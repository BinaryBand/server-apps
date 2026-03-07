from __future__ import annotations

from pathlib import Path

from src.utils.secrets import REPO_ROOT, read_secret


def repo_root() -> Path:
    return REPO_ROOT


def _resolve_host_path(env_key: str, default_relative: str) -> Path:
    value = read_secret(env_key)
    if value:
        return Path(value).expanduser().resolve()
    return (repo_root() / default_relative).resolve()


def local_root() -> Path:
    return (repo_root() / "runtime").resolve()


def media_root() -> Path:
    return _resolve_host_path("MEDIA_DATA_PATH", "runtime/media")


def logs_root() -> Path:
    return _resolve_host_path("LOGS_DIR", "runtime/logs")


def backups_root() -> Path | None:
    value = read_secret("BACKUPS_DIR")
    if not value:
        return None
    return Path(value).expanduser().resolve()


def restic_repo_root() -> Path | None:
    value = read_secret("RESTIC_REPO_DIR")
    if not value:
        return None
    return Path(value).expanduser().resolve()


def project_name(default: str | None = None) -> str:
    if default is None:
        default = repo_root().name
    return read_secret("PROJECT_NAME") or default
