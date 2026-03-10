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


def runtime_root() -> Path:
    return (repo_root() / "runtime").resolve()


def _resolve_runtime_dir(env_key: str, default_relative: str) -> Path:
    value = read_secret(env_key)
    if value:
        return Path(value).expanduser().resolve()
    return (repo_root() / default_relative).resolve()


def state_root() -> Path:
    return _resolve_runtime_dir("STATE_DIR", "runtime/state")


def checkpoints_root() -> Path:
    return _resolve_runtime_dir("CHECKPOINTS_DIR", "runtime/checkpoints")


def locks_root() -> Path:
    return _resolve_runtime_dir("LOCKS_DIR", "runtime/locks")


def ensure_runtime_dirs() -> None:
    for path in (runtime_root(), state_root(), checkpoints_root(), locks_root()):
        path.mkdir(parents=True, exist_ok=True)
