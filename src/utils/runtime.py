from __future__ import annotations

from pathlib import Path

from src.utils.secrets import REPO_ROOT, read_secret


def repo_root() -> Path:
    return REPO_ROOT


def local_root() -> Path:
    return repo_root() / ".local"


def project_name(default: str | None = None) -> str:
    if default is None:
        default = repo_root().name
    return read_secret("PROJECT_NAME") or default
