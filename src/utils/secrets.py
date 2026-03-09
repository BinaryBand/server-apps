from __future__ import annotations

from dotenv import find_dotenv, load_dotenv
from typing import overload
import os


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
