from __future__ import annotations

from pathlib import Path
import os

from dotenv import find_dotenv, load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = REPO_ROOT / ".env"

_env_path = DEFAULT_ENV_PATH
_loaded = False


def _resolve_env_path() -> Path:
    found = find_dotenv(usecwd=True)
    if found:
        return Path(found)
    return DEFAULT_ENV_PATH


def load_env(path: str | Path | None = None, *, override: bool = False) -> Path:
    global _env_path, _loaded

    target = Path(path) if path is not None else _resolve_env_path()
    if not target.is_absolute():
        target = (REPO_ROOT / target).resolve()

    load_dotenv(target, override=override)
    _env_path = target
    _loaded = True
    return _env_path


def env_path() -> Path:
    if not _loaded:
        load_env()
    return _env_path


def _save_to_env(key: str, value: str) -> None:
    target = env_path()
    lines = []
    if target.exists():
        with open(target, "r", encoding="utf8") as f:
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

    with open(target, "w", encoding="utf8") as f:
        f.write("\n".join(out) + "\n")
    os.environ[key] = value


def _remove_from_env(path: str, key: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf8") as f:
        lines = f.read().splitlines()
    out = [ln for ln in lines if not ln.strip().startswith(f"{key}=")]
    with open(path, "w", encoding="utf8") as f:
        f.write("\n".join(out) + ("\n" if out else ""))
    os.environ.pop(key, None)


def secret_service_name() -> str:
    return env_path().stem


def read_secret(name: str, default: str | None = None) -> str | None:
    if not _loaded:
        load_env()
    return os.getenv(name, default)


def read_secret_required(name: str) -> str:
    value = read_secret(name)
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


def read_all_secrets() -> dict[str, str]:
    if not _loaded:
        load_env()
    return dict(os.environ)


def write_secret(name: str, value: str) -> str:
    _save_to_env(name, value)
    return str(env_path())


def has_secrets(*names: str) -> bool:
    return all(read_secret(name) for name in names)


def delete_secret(name: str) -> None:
    _remove_from_env(str(env_path()), name)


# Ensure environment is available on first import for existing callers.
load_env()
