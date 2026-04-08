from __future__ import annotations

import src.backup.restore as _impl

# Compatibility aliases for legacy monkeypatch targets.
restic = _impl.restic
rclone_sync = _impl.rclone_sync
storage_mount_source = _impl.storage_mount_source
logical_volume_mount_source = _impl.logical_volume_mount_source
logical_volume_names = _impl.logical_volume_names
_impl_pull_restic_from_cloud = _impl.pull_restic_from_cloud


def pull_restic_from_cloud() -> None:
    _impl.restic = restic
    _impl.rclone_sync = rclone_sync
    _impl.storage_mount_source = storage_mount_source
    _impl.logical_volume_mount_source = logical_volume_mount_source
    _impl.logical_volume_names = logical_volume_names
    return _impl_pull_restic_from_cloud()


def recent_snapshots(limit: int = 10) -> str:
    _impl.restic = restic
    _impl.rclone_sync = rclone_sync
    _impl.storage_mount_source = storage_mount_source
    _impl.logical_volume_mount_source = logical_volume_mount_source
    _impl.logical_volume_names = logical_volume_names
    _impl.pull_restic_from_cloud = pull_restic_from_cloud
    return _impl.recent_snapshots(limit)


def restore_snapshot(
    snapshot: str = "latest",
    target: str = "/backups/restore",
    no_apply_volumes: bool = False,
) -> None:
    _impl.restic = restic
    _impl.rclone_sync = rclone_sync
    _impl.storage_mount_source = storage_mount_source
    _impl.logical_volume_mount_source = logical_volume_mount_source
    _impl.logical_volume_names = logical_volume_names
    _impl.pull_restic_from_cloud = pull_restic_from_cloud
    return _impl.restore_snapshot(snapshot, target, no_apply_volumes)


__all__ = ["recent_snapshots", "restore_snapshot", "pull_restic_from_cloud"]
