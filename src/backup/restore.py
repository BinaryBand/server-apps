import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

import src.backup.restic as restic
from src.storage.volumes import (
    logical_volume_mount_source,
    logical_volume_names,
    storage_docker_mount_flags,
    storage_mount_source,
)
from src.toolbox.core.config import restic_pcloud_sync_enabled
from src.toolbox.docker.wrappers.rclone import rclone_sync


def recent_snapshots(limit: int = 10) -> str:
    """Return a recent restic snapshot listing after refreshing the local repo."""
    pull_restic_from_cloud()

    try:
        return restic.run_restic_command_with_output(["snapshots", "--latest", str(limit)])
    except restic.ResticRunnerError as err:
        raise RuntimeError(f"[recent_snapshots] snapshot listing failed: {err}") from err


def _sync_volume_path_to_target(
    backups_volume_name: str,
    source_relative_path: str,
    target_mount: str,
) -> None:
    docker_args = ["-e", "RCLONE_CONFIG=/dev/null"]
    docker_args += ["-v", f"{backups_volume_name}:/source-root:ro"]
    docker_args += ["-v", f"{target_mount}:/dest"]

    rclone_sync(f"/source-root/{source_relative_path}", "/dest", docker_args=docker_args)


def _volume_subdir_exists(volume_name: str, relative_path: str) -> bool:
    probe = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{volume_name}:/source-root:ro",
            "alpine:3.20",
            "test",
            "-d",
            f"/source-root/{relative_path}",
        ],
        check=False,
    )
    return probe.returncode == 0


def pull_restic_from_cloud() -> None:
    """Sync restic repository from pCloud before restore."""
    if not restic_pcloud_sync_enabled():
        print("Skipping restic pCloud sync (RESTIC_PCLOUD_SYNC disabled).")
        return

    docker_args = storage_docker_mount_flags("restic_repo", "/repo")
    docker_args += storage_docker_mount_flags("rclone_config", "/config/rclone", read_only=True)
    docker_args += ["-e", "RCLONE_CONFIG=/config/rclone/rclone.conf"]

    try:
        rclone_sync(restic.RESTIC_PCLOUD_REMOTE, "/repo", docker_args=docker_args)
    except RuntimeError as err:
        raise RuntimeError(
            f"[pull_restic_from_cloud] restic repository sync failed: {err}"
        ) from err


def _find_source_path(backups_volume_name: str, source_name: str, target_prefix: str) -> str | None:
    """Find source path for a logical volume in backup volume candidates."""
    candidates = [
        f"{target_prefix}volumes/{source_name}",
        f"{target_prefix}backups/volumes/{source_name}",
    ]
    return next(
        (
            candidate
            for candidate in candidates
            if _volume_subdir_exists(backups_volume_name, candidate)
        ),
        None,
    )


def _apply_restored_volumes_from_backups_volume(target: str) -> None:
    backups_volume_name = storage_mount_source("backups")
    target_prefix = ""
    if target != "/backups":
        target_prefix = target.removeprefix("/backups/").strip("/") + "/"

    for source_name in logical_volume_names():
        source_relative_path = _find_source_path(backups_volume_name, source_name, target_prefix)

        if source_relative_path is None:
            print(f"Skipping {source_name}; not found in backups.")
            continue

        target_mount = logical_volume_mount_source(source_name)

        print(f"Applying restored data: {source_relative_path} -> {target_mount}")
        _sync_volume_path_to_target(backups_volume_name, source_relative_path, target_mount)


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
    pull_restic_from_cloud()
    restic.run_restic_command(["restore", snapshot, "--target", target])

    if no_apply_volumes:
        return

    if target.startswith("/backups"):
        _apply_restored_volumes_from_backups_volume(target)
        return

    print("Restore target is outside /backups; skipping volume apply step.")


__all__ = ["recent_snapshots", "restore_snapshot", "pull_restic_from_cloud"]
