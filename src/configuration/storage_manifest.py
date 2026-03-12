# Declarative storage manifest — single source of truth for volume topology.
#
# LOGICAL_VOLUME_NAMES  — Docker named volumes backing live app data. Each name
#                         matches the canonical external Docker volume name used in
#                         compose (e.g. "jellyfin_config" → cloud_jellyfin_config).
#
# STORAGE_TARGETS       — Operational volumes used by backup/restore tooling.
#                         Keys are semantic names; values are (service, container_path)
#                         tuples used to locate the backing volume via compose.
#
# BIND_MOUNT_ENV        — Logical volume names that are host bind-mounts rather than
#                         named Docker volumes, mapped to the env var that supplies
#                         the host path.

LOGICAL_VOLUME_NAMES: list[str] = [
    "jellyfin_config",
    "jellyfin_data",
    "baikal_config",
    "baikal_data",
    "minio_data",
]

STORAGE_TARGETS: dict[str, tuple[str, str]] = {
    "backups": ("restic", "/backups"),
    "restic_repo": ("restic", "/repo"),
    "rclone_config": ("rclone", "/config/rclone"),
}

BIND_MOUNT_ENV: dict[str, str] = {
    "minio_data": "MINIO_DATA_DIR",
}

__all__ = [
    "LOGICAL_VOLUME_NAMES",
    "STORAGE_TARGETS",
    "BIND_MOUNT_ENV",
]
