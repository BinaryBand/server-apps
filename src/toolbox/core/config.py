from __future__ import annotations

from src.toolbox.core.secrets import read_secret


def get_project_name() -> str:
    return read_secret("PROJECT_NAME", "cloud-apps")


def rclone_remote(default: str = "pcloud") -> str:
    return read_secret("RCLONE_REMOTE", default) or default


def rclone_version(default: str = "latest") -> str:
    return read_secret("RCLONE_VERSION", default) or default


def restic_version(default: str = "latest") -> str:
    return read_secret("RESTIC_VERSION", default) or default


def restic_pcloud_remote(default: str = "pcloud:Backups/Restic") -> str:
    return read_secret("RESTIC_PCLOUD_REMOTE", default) or default


def restic_pcloud_sync_enabled() -> bool:
    return read_secret("RESTIC_PCLOUD_SYNC", "1") not in {
        "0",
        "false",
        "False",
        "no",
        "NO",
    }


def runbook_resume_enabled() -> bool:
    return read_secret("RUNBOOK_RESUME", "0") in {"1", "true", "True", "yes"}


def bind_mount_value(env_key: str, default: str | None = None) -> str | None:
    return read_secret(env_key) or default


__all__ = [
    "get_project_name",
    "rclone_remote",
    "rclone_version",
    "restic_version",
    "restic_pcloud_remote",
    "restic_pcloud_sync_enabled",
    "runbook_resume_enabled",
    "bind_mount_value",
]
