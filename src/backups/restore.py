from pathlib import Path
import shutil
import subprocess

from src.utils.runtime import project_name, repo_root
from src.utils.secrets import load_env, read_secret

RCLONE_IMAGE: str = str(
    read_secret("RCLONE_IMAGE")
    or f"rclone/rclone:{read_secret('RCLONE_VERSION','latest')}"
)
RESTIC_PCLOUD_REMOTE: str = str(
    read_secret("RESTIC_PCLOUD_REMOTE", "pcloud:Backups/Restic")
)


def _run(cmd: list[str]) -> None:
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _normalize_permissions_for_reset(repo_root_path: Path) -> None:
    apply_perms_script = repo_root_path / "scripts" / "apply-perms.sh"
    if not apply_perms_script.exists():
        raise SystemExit(f"Permissions script not found: {apply_perms_script}")
    _run(["bash", str(apply_perms_script), "--reset"])


def _resolve_host_restore_dir(repo_root: Path, target: str) -> Path | None:
    backups_root = repo_root / ".local" / "backups"
    if target == "/backups":
        return backups_root
    if target.startswith("/backups/"):
        relative = target.removeprefix("/backups/")
        return backups_root / relative
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
        ]
    )


def pull_restic_repo_from_pcloud() -> None:
    """Sync restic repository from pCloud before restore."""
    if read_secret("RESTIC_PCLOUD_SYNC", "1") in {"0", "false", "False", "no", "NO"}:
        print("Skipping restic pCloud sync (RESTIC_PCLOUD_SYNC disabled).")
        return

    root = repo_root()
    local_repo = root / ".local" / "restic"
    rclone_config_dir = root / ".local" / "rclone"
    rclone_config_file = rclone_config_dir / "rclone.conf"

    if not rclone_config_file.exists():
        print(
            f"Skipping restic pCloud sync; rclone config not found: {rclone_config_file}"
        )
        return

    local_repo.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{str(local_repo.resolve())}:/repo",
        "-v",
        f"{str(rclone_config_dir.resolve())}:/config/rclone:ro",
        "-e",
        "RCLONE_CONFIG=/config/rclone/rclone.conf",
        RCLONE_IMAGE,
        "sync",
        RESTIC_PCLOUD_REMOTE,
        "/repo",
    ]
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print("Repairing repository permissions via Ansible reset mode and retrying...")
        _normalize_permissions_for_reset(root)
        subprocess.run(cmd, check=True)


def _apply_restored_volumes(
    repo_root: Path, project: str, host_restore_dir: Path
) -> None:
    candidate_roots = [
        host_restore_dir / "volumes",
        host_restore_dir / "backups" / "volumes",
    ]
    restore_volumes_root = None
    for candidate in candidate_roots:
        try:
            if candidate.exists():
                restore_volumes_root = candidate
                break
        except PermissionError:
            print(
                f"Skipping inaccessible restore path (permission denied): {candidate}"
            )
    if restore_volumes_root is None:
        print(
            "No restored volume tree found. Checked: "
            + ", ".join(str(p) for p in candidate_roots)
        )
        return

    mappings = [
        ("jellyfin_config", f"{project}_jellyfin_config"),
        ("jellyfin_data", f"{project}_jellyfin_data"),
        ("baikal_config", f"{project}_baikal_config"),
        ("baikal_data", f"{project}_baikal_data"),
        ("minio_data", f"{project}_minio_data"),
    ]

    for source_name, volume_name in mappings:
        source_dir = restore_volumes_root / source_name
        if not source_dir.exists():
            print(f"Skipping {source_name}; not present in restored snapshot.")
            continue
        print(f"Applying restored data: {source_name} -> {volume_name}")
        _sync_dir_to_volume(source_dir, volume_name)


def _preflight_restore_target(
    repo_root_path: Path, target: str, host_restore_dir: Path | None
) -> None:
    if host_restore_dir is not None and target == "/backups/restore":
        _normalize_permissions_for_reset(repo_root_path)
    if (
        host_restore_dir is not None
        and target == "/backups/restore"
        and host_restore_dir.exists()
    ):
        print(f"Clearing existing restore directory: {host_restore_dir}")
        shutil.rmtree(host_restore_dir)


def _execute_restore(snapshot: str, target: str) -> None:
    from src.backups.restic_runner import run_restic_command

    pull_restic_repo_from_pcloud()
    run_restic_command(["restore", snapshot, "--target", target])


def _post_restore_permissions(
    repo_root_path: Path, target: str, host_restore_dir: Path | None
) -> None:
    if host_restore_dir is not None and target.startswith("/backups/"):
        _normalize_permissions_for_reset(repo_root_path)


def _post_restore_apply(
    repo_root_path: Path,
    project: str,
    host_restore_dir: Path | None,
    no_apply_volumes: bool,
) -> None:
    if no_apply_volumes:
        return

    if host_restore_dir is None:
        print("Restore target is outside /backups; skipping volume apply step.")
        return

    _apply_restored_volumes(repo_root_path, project, host_restore_dir)


def restore_snapshot(
    snapshot: str = "latest",
    target: str = "/backups/restore",
    project: str | None = None,
    no_apply_volumes: bool = False,
) -> None:
    """Run restic restore into `target` then copy restored volume trees back into docker volumes.

    - `snapshot`: restic snapshot id or 'latest'
    - `target`: restore path inside restic container (e.g. '/backups/restore')
    - `project`: compose project name used as volume name prefix; if None, uses cwd name
    - `no_apply_volumes`: if True, do not copy restored files into docker volumes
    """
    load_env()
    root = repo_root()
    project = project or project_name()

    host_restore_dir = _resolve_host_restore_dir(root, target)
    _preflight_restore_target(root, target, host_restore_dir)
    _execute_restore(snapshot, target)
    _post_restore_permissions(root, target, host_restore_dir)
    _post_restore_apply(root, project, host_restore_dir, no_apply_volumes)
