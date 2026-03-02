from __future__ import annotations

from dotenv import load_dotenv, find_dotenv
from pathlib import Path
import os


path = Path(find_dotenv())
load_dotenv(path)


def _save_to_env(key: str, value: str) -> None:
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf8") as f:
            lines = f.read().splitlines()

    out = []
    found = False
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")

    with open(path, "w", encoding="utf8") as f:
        f.write("\n".join(out) + "\n")


def _remove_from_env(path: str, key: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf8") as f:
        lines = f.read().splitlines()
    out = [ln for ln in lines if not ln.strip().startswith(f"{key}=")]
    with open(path, "w", encoding="utf8") as f:
        f.write("\n".join(out) + ("\n" if out else ""))


def secret_service_name() -> str:
    return path.stem


def read_secret(name: str) -> str | None:
    return os.getenv(name)


def write_secret(name: str, value: str) -> str:
    _save_to_env(name, value)
    return str(path)


def has_secrets(*names: str) -> bool:
    return all(read_secret(name) for name in names)


def delete_secret(name: str) -> None:
    _remove_from_env(str(path), name)
