from __future__ import annotations

from src.toolbox.core.config import secret

from from_root import from_root
from pathlib import Path


PROJECT_NAME = "cloud-apps"


def repo_root() -> Path:
    return from_root("pyproject.toml").parent


def _resolve_host_path(env_key: str, default_relative: str) -> Path:
    value: str | None = secret(env_key)
    if value:
        return Path(value).expanduser().resolve()
    return (repo_root() / default_relative).resolve()


def media_root() -> Path:
    return _resolve_host_path("MEDIA_DATA_PATH", "runtime/media")


def logs_root() -> Path:
    return _resolve_host_path("LOGS_DIR", "runtime/logs")


def runtime_root() -> Path:
    return (repo_root() / "runtime").resolve()


def state_root() -> Path:
    return _resolve_host_path("STATE_DIR", "runtime/state")


def checkpoints_root() -> Path:
    return _resolve_host_path("CHECKPOINTS_DIR", "runtime/checkpoints")


def locks_root() -> Path:
    return _resolve_host_path("LOCKS_DIR", "runtime/locks")


def ensure_runtime_dirs() -> None:
    for path in (runtime_root(), state_root(), checkpoints_root(), locks_root()):
        path.mkdir(parents=True, exist_ok=True)


__all__ = [
    "PROJECT_NAME",
    "repo_root",
    "media_root",
    "logs_root",
    "runtime_root",
    "state_root",
    "checkpoints_root",
    "locks_root",
    "ensure_runtime_dirs",
]
