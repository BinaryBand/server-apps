from __future__ import annotations

from typing import Optional

from src.toolbox.core.runtime import repo_root
from src.toolbox.core.secrets import read_secret

try:
    from src.configuration.rclone_config import RcloneConfig
except Exception:
    RcloneConfig = None  # type: ignore


def get_project_name() -> str:
    return read_secret("PROJECT_NAME", "cloud-apps")


_RCLONE_CFG: Optional[RcloneConfig]


def _load_rclone_config() -> Optional[RcloneConfig]:
    global _RCLONE_CFG
    if RcloneConfig is None:
        _RCLONE_CFG = None
        return None
    if '_RCLONE_CFG' in globals() and _RCLONE_CFG is not None:
        return _RCLONE_CFG
    cfg_path = repo_root() / "configs" / "rclone.toml"
    try:
        if cfg_path.exists():
            _RCLONE_CFG = RcloneConfig.from_toml(cfg_path)
        else:
            _RCLONE_CFG = RcloneConfig()
    except Exception:
        _RCLONE_CFG = RcloneConfig()
    return _RCLONE_CFG


def rclone_remote(default: str = "pcloud") -> str:
    cfg = _load_rclone_config()
    if cfg and getattr(cfg, "remote", None):
        return cfg.remote
    return read_secret("RCLONE_REMOTE", default) or default


def rclone_version(default: str = "latest") -> str:
    cfg = _load_rclone_config()
    if cfg and getattr(cfg, "version", None):
        return cfg.version
    return read_secret("RCLONE_VERSION", default) or default


def rclone_transfers(default: str = "1") -> str:
    cfg = _load_rclone_config()
    if cfg and getattr(cfg, "transfers", None) is not None:
        return str(cfg.transfers)
    return read_secret("RCLONE_TRANSFERS", default) or default


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
    "rclone_transfers",
]
