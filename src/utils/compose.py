from __future__ import annotations

import subprocess

from src.utils.secrets import read_secret
from src.utils.runtime import repo_root


COMPOSE_FILES: tuple[str, str] = ("compose/base.yml", "compose/dev.yml")
EXTERNAL_VOLUME_SUFFIXES: tuple[str, ...] = (
    "baikal_config",
    "baikal_data",
    "jellyfin_config",
    "jellyfin_cache",
    "jellyfin_data",
    "minio_data",
)


def compose_base_cmd() -> list[str]:
    compose_cmd = read_secret("DOCKER_COMPOSE_CMD") or "docker compose"
    return compose_cmd.split()


def compose_file_args() -> list[str]:
    root = repo_root()
    env_file = root / ".env"
    compose_files = [root / path for path in COMPOSE_FILES]
    return [
        "--project-directory",
        str(root),
        "--env-file",
        str(env_file),
        "-f",
        str(compose_files[0]),
        "-f",
        str(compose_files[1]),
    ]


def compose_cmd(*args: str) -> list[str]:
    return [*compose_base_cmd(), *compose_file_args(), *args]


def required_external_volume_names() -> list[str]:
    project_prefix = read_secret("PROJECT_NAME", "server-apps") or "server-apps"
    return [f"{project_prefix}_{suffix}" for suffix in EXTERNAL_VOLUME_SUFFIXES]


def ensure_external_volumes() -> None:
    for volume_name in required_external_volume_names():
        subprocess.run(["docker", "volume", "create", volume_name], check=True)
