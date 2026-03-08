from __future__ import annotations

from dotenv import find_dotenv, load_dotenv
from pathlib import Path
import os


_loaded = False


def _env_path():
    return Path(find_dotenv())


def _save_to_env(key: str, value: str) -> None:
    target: Path = _env_path()
    lines: list[str] = []
    if target.exists():
        with open(target, "r", encoding="utf8") as f:
            lines = f.read().splitlines()

    out: list[str] = []
    found = False
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")

    with open(target, "w", encoding="utf8") as f:
        f.write("\n".join(out) + "\n")
    os.environ[key] = value


def _remove_from_env(path: str, key: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf8") as f:
        lines: list[str] = f.read().splitlines()
    out: list[str] = [ln for ln in lines if not ln.strip().startswith(f"{key}=")]
    with open(path, "w", encoding="utf8") as f:
        f.write("\n".join(out) + ("\n" if out else ""))
    os.environ.pop(key, None)


def read_all_secrets() -> dict[str, str]:
    if not _loaded:
        load_dotenv()
    return dict(os.environ)


def read_secret(name: str, default: str | None = None) -> str | None:
    if not _loaded:
        load_dotenv()
    return os.getenv(name, default)


def read_secret_required(name: str) -> str:
    value: str | None = read_secret(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def read_secret_alias(
    primary: str,
    *aliases: str,
    default: str | None = None,
    required: bool = False,
) -> str | None:
    for key in (primary, *aliases):
        value = read_secret(key)
        if value:
            return value
    if required:
        keys = ", ".join((primary, *aliases))
        raise SystemExit(f"Missing required environment variable(s): {keys}")
    return default


def write_secret(name: str, value: str) -> str:
    _save_to_env(name, value)
    return str(_env_path())


def has_secrets(*names: str) -> bool:
    return all(read_secret(name) for name in names)


def delete_secret(name: str) -> None:
    _remove_from_env(str(_env_path()), name)
