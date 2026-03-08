from src.utils.docker import volumes as volatile
from src.utils.runtime import PROJECT_NAME
from src.utils.docker.wrappers.rclone import rclone_sync
from src.utils.docker.wrappers import restic
from src.utils.secrets import read_secret

import subprocess


RESTIC_PCLOUD_REMOTE: str = str(
    read_secret("RESTIC_PCLOUD_REMOTE", "pcloud:Backups/Restic")
)


class RestoreRunnerError(RuntimeError):
    """Raised when restore execution commands fail."""


def _sync_volume_path_to_target(
    backups_volume_name: str,
    source_relative_path: str,
    target_mount: str,
) -> None:
    docker_args = ["-e", "RCLONE_CONFIG=/dev/null"]
    docker_args += ["-v", f"{backups_volume_name}:/source-root:ro"]
    docker_args += ["-v", f"{target_mount}:/dest"]

    rclone_sync(
        f"/source-root/{source_relative_path}", "/dest", docker_args=docker_args
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

    docker_args = volatile.storage_docker_mount_flags(
        PROJECT_NAME, "restic_repo", "/repo"
    )
    docker_args += volatile.storage_docker_mount_flags(
        PROJECT_NAME, "rclone_config", "/config/rclone", read_only=True
    )
    docker_args += ["-e", "RCLONE_CONFIG=/config/rclone/rclone.conf"]

    try:
        rclone_sync(RESTIC_PCLOUD_REMOTE, "/repo", docker_args=docker_args)
    except Exception as err:
        raise RestoreRunnerError(f"restic repository sync failed: {err}") from err


def _apply_restored_volumes_from_backups_volume(project: str, target: str) -> None:
    backups_volume_name = volatile.storage_mount_source(project, "backups")
    target_prefix = ""
    if target != "/backups":
        target_prefix = target.removeprefix("/backups/").strip("/") + "/"

    for source_name in volatile.LOGICAL_VOLUMES:
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

        override = volatile.host_bind_path(source_name)
        target_mount = (
            str(override.resolve())
            if override
            else volatile.docker_volume_name(project, source_name)
        )

        print(
            f"Applying restored data from backups volume: {source_relative_path} -> {target_mount}"
        )
        _sync_volume_path_to_target(
            backups_volume_name, source_relative_path, target_mount
        )


def restore_snapshot(
    snapshot: str = "latest",
    target: str = "/backups/restore",
    no_apply_volumes: bool = False,
) -> None:
    """Run restic restore into `target` then copy restored volume trees back into docker volumes.

    - `snapshot`: restic snapshot id or 'latest'
    - `target`: restore path inside restic container (e.g. '/backups/restore')
    - `no_apply_volumes`: if True, do not copy restored files into docker volumes
    """
    # ensure local restic repository is refreshed from remote before restore
    pull_restic_repo_from_pcloud()

    # perform restic restore
    restic.run_restic_command(["restore", snapshot, "--target", target])

    if no_apply_volumes:
        return

    if target.startswith("/backups"):
        _apply_restored_volumes_from_backups_volume(PROJECT_NAME, target)
        return

    print("Restore target is outside /backups; skipping volume apply step.")
