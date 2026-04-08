from __future__ import annotations

import os
from typing import overload

from dotenv import find_dotenv, load_dotenv

_loaded = False


def _load_env_once() -> None:
    global _loaded
    if _loaded:
        return
    load_dotenv(find_dotenv())
    _loaded = True


@overload
def read_secret(name: str) -> str | None: ...


@overload
def read_secret(name: str, default: str) -> str: ...


def read_secret(name: str, default: str | None = None) -> str | None:
    _load_env_once()
    return os.getenv(name, default)


def secret(name: str, default: str | None = None) -> str | None:
    return read_secret(name, default)


def minio_credentials() -> tuple[str, str]:
    user = read_secret("MINIO_ROOT_USER") or read_secret("S3_ACCESS_KEY")
    password = read_secret("MINIO_ROOT_PASSWORD") or read_secret("S3_SECRET_KEY")
    if not user or not password:
        raise RuntimeError("Missing MinIO credentials")
    return user, password


__all__ = ["read_secret", "secret", "minio_credentials"]
