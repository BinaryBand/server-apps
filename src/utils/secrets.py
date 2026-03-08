from __future__ import annotations

from dotenv import find_dotenv, load_dotenv
import os


_loaded = False


def _load_env_once() -> None:
    global _loaded
    if _loaded:
        return
    load_dotenv(find_dotenv())
    _loaded = True


def read_secret(name: str, default: str | None = None) -> str | None:
    _load_env_once()
    return os.getenv(name, default)
