from pathlib import Path
import shutil
import subprocess

from src.utils.secrets import load_env, read_secret
from src.utils.runtime import backups_root
from src.utils import volumes as volutils

RCLONE_IMAGE: str = str(
    read_secret("RCLONE_IMAGE")
    or f"rclone/rclone:{read_secret('RCLONE_VERSION','latest')}"
)
RESTIC_PCLOUD_REMOTE: str = str(
    read_secret("RESTIC_PCLOUD_REMOTE", "pcloud:Backups/Restic")
)


class RestoreRunnerError(RuntimeError):
    """Raised when restore execution commands fail."""


def _run(cmd: list[str]) -> None:
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise RestoreRunnerError(
            f"restore command failed with exit code {err.returncode}: {' '.join(cmd)}"
        ) from err


def _resolve_host_restore_dir(repo_root: Path, target: str) -> Path | None:
    backups_override = backups_root()
    if not backups_override:
        return None

    if target == "/backups":
        return backups_override
    if target.startswith("/backups/"):
        relative = target.removeprefix("/backups/")
        return backups_override / relative
    return None


def _sync_dir_to_volume(source_dir: Path, volume_name: str) -> None:
    _run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            "RCLONE_CONFIG=/dev/null",
            "-v",
            f"{str(source_dir.resolve())}:/source:ro",
            "-v",
            f"{volume_name}:/dest",
            RCLONE_IMAGE,
            "sync",
            "/source",
            "/dest",
            '--progress',
        ]
    )


def _sync_volume_path_to_target(
    backups_volume_name: str,
    source_relative_path: str,
    target_mount: str,
) -> None:
    _run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            "RCLONE_CONFIG=/dev/null",
            "-v",
            f"{backups_volume_name}:/source-root:ro",
            "-v",
            f"{target_mount}:/dest",
            RCLONE_IMAGE,
            "sync",
            f"/source-root/{source_relative_path}",
            "/dest",
            "--progress",
        ]
    )


def _volume_subdir_exists(volume_name: str, relative_path: str) -> bool:
    probe = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{volume_name}:/source-root:ro",
            "alpine:3.20",
            "sh",
            "-lc",
            f"test -d '/source-root/{relative_path}'",
        ],
        check=False,
    )
    return probe.returncode == 0


def pull_restic_repo_from_pcloud() -> None:
    """Sync restic repository from pCloud before restore."""
    if read_secret("RESTIC_PCLOUD_SYNC", "1") in {"0", "false", "False", "no", "NO"}:
        print("Skipping restic pCloud sync (RESTIC_PCLOUD_SYNC disabled).")
        return

    repo_root = Path(__file__).resolve().parents[2]
    project = read_secret("PROJECT_NAME") or repo_root.name

    cmd = [
        "docker",
        "run",
        "--rm",
        *volutils.storage_docker_mount_flags(project, "restic_repo", "/repo"),
        *volutils.storage_docker_mount_flags(
            project,
            "rclone_config",
            "/config/rclone",
            read_only=True,
        ),
        "-e",
        "RCLONE_CONFIG=/config/rclone/rclone.conf",
        RCLONE_IMAGE,
        "sync",
        RESTIC_PCLOUD_REMOTE,
        "/repo",
        '--progress',
    ]
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise RestoreRunnerError(
            f"restic repository sync failed with exit code {err.returncode}: {' '.join(cmd)}"
        ) from err


def _apply_restored_volumes(
    repo_root: Path, project: str, host_restore_dir: Path
) -> None:
    candidate_roots = [
        host_restore_dir / "volumes",
        host_restore_dir / "backups" / "volumes",
    ]
    restore_volumes_root = next((p for p in candidate_roots if p.exists()), None)
    if restore_volumes_root is None:
        print(
            "No restored volume tree found. Checked: "
            + ", ".join(str(p) for p in candidate_roots)
        )
        return

    mappings = list(volutils.LOGICAL_VOLUMES)

    for source_name in mappings:
        source_dir = restore_volumes_root / source_name
        if not source_dir.exists():
            print(f"Skipping {source_name}; not present in restored snapshot.")
            continue

        override = volutils.host_bind_path(source_name)
        target_mount = (
            str(override.resolve()) if override else volutils.docker_volume_name(project, source_name)
        )
        print(f"Applying restored data: {source_name} -> {target_mount}")
        _sync_dir_to_volume(source_dir, target_mount)


def _apply_restored_volumes_from_backups_volume(project: str, target: str) -> None:
    backups_volume_name, _ = volutils.storage_mount_source(project, "backups")
    target_prefix = ""
    if target != "/backups":
        target_prefix = target.removeprefix("/backups/").strip("/") + "/"

    for source_name in volutils.LOGICAL_VOLUMES:
        candidates = [
            f"{target_prefix}volumes/{source_name}",
            f"{target_prefix}backups/volumes/{source_name}",
        ]
        source_relative_path = next(
            (
                candidate
                for candidate in candidates
                if _volume_subdir_exists(backups_volume_name, candidate)
            ),
            None,
        )

        if source_relative_path is None:
            print(
                f"Skipping {source_name}; not present in restored snapshot paths {', '.join(candidates)}."
            )
            continue

        override = volutils.host_bind_path(source_name)
        target_mount = (
            str(override.resolve()) if override else volutils.docker_volume_name(project, source_name)
        )

        print(
            f"Applying restored data from backups volume: {source_relative_path} -> {target_mount}"
        )
        _sync_volume_path_to_target(backups_volume_name, source_relative_path, target_mount)


def restore_snapshot(
    snapshot: str = "latest",
    target: str = "/backups/restore",
    project: str | None = None,
    no_apply_volumes: bool = False,
    allow_destructive_apply: bool = False,
) -> None:
    """Run restic restore into `target` then copy restored volume trees back into docker volumes.

    - `snapshot`: restic snapshot id or 'latest'
    - `target`: restore path inside restic container (e.g. '/backups/restore')
    - `project`: compose project name used as volume name prefix; if None, uses cwd name
    - `no_apply_volumes`: if True, do not copy restored files into docker volumes
    """
    load_env()
    from src.backups.restic_runner import run_restic_command

    repo_root = Path(__file__).resolve().parents[2]
    project = project or read_secret("PROJECT_NAME") or repo_root.name

    host_restore_dir = _resolve_host_restore_dir(repo_root, target)
    if (
        host_restore_dir is not None
        and target == "/backups/restore"
        and host_restore_dir.exists()
    ):
        print(f"Clearing existing restore directory: {host_restore_dir}")
        shutil.rmtree(host_restore_dir)

    # ensure local restic repository is refreshed from remote before restore
    pull_restic_repo_from_pcloud()

    # perform restic restore
    run_restic_command(["restore", snapshot, "--target", target])

    if no_apply_volumes:
        return

    if not allow_destructive_apply:
        raise RestoreRunnerError(
            "Restore apply uses destructive sync semantics. "
            "Pass allow_destructive_apply=True only when intentional."
        )

    if host_restore_dir is not None:
        _apply_restored_volumes(repo_root, project, host_restore_dir)
        return

    if target.startswith("/backups"):
        _apply_restored_volumes_from_backups_volume(project, target)
        return

    print("Restore target is outside /backups; skipping volume apply step.")
