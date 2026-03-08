from __future__ import annotations

from src.utils.secrets import read_secret

from from_root import from_root
from pathlib import Path


PROJECT_NAME = "cloud-apps"


def repo_root() -> Path:
    return from_root("pyproject.toml").parent


def _resolve_host_path(env_key: str, default_relative: str) -> Path:
    value = read_secret(env_key)
    if value:
        return Path(value).expanduser().resolve()
    return (repo_root() / default_relative).resolve()


def media_root() -> Path:
    return _resolve_host_path("MEDIA_DATA_PATH", "runtime/media")


def logs_root() -> Path:
    return _resolve_host_path("LOGS_DIR", "runtime/logs")


def backups_root() -> Path | None:
    value: str | None = read_secret("BACKUPS_DIR")
    if not value:
        return None
    return Path(value).expanduser().resolve()


def restic_repo_root() -> Path | None:
    value: str | None = read_secret("RESTIC_REPO_DIR")
    if not value:
        return None
    return Path(value).expanduser().resolve()
