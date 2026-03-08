from __future__ import annotations

from src.utils.runtime import PROJECT_NAME, repo_root

from pathlib import Path
import dotenv
import subprocess


DOCKER_COMPOSE_CMD: list[str] = ["docker", "compose"]

COMPOSE_FILES: tuple[str, str] = ("compose/base.yml", "compose/dev.yml")
EXTERNAL_VOLUME_SUFFIXES: tuple[str, ...] = (
    "jellyfin_config",
    "jellyfin_data",
    "baikal_config",
    "baikal_data",
    "restic_repo_data",
)


def _compose_file_args() -> list[str]:
    root: Path = repo_root()
    env: str = dotenv.find_dotenv()

    cmd = [
        "--project-name",
        PROJECT_NAME,
        "--project-directory",
        str(root),
        "--env-file",
        env,
    ]

    for file in COMPOSE_FILES:
        file_path = str(root / file)
        cmd += ["-f", file_path]

    return cmd


def compose_cmd(*args: str) -> list[str]:
    return [*DOCKER_COMPOSE_CMD, *_compose_file_args(), *args]


def required_external_volume_names() -> list[str]:
    return [f"{PROJECT_NAME}_{suffix}" for suffix in EXTERNAL_VOLUME_SUFFIXES]


def ensure_external_volumes() -> None:
    for volume_name in required_external_volume_names():
        subprocess.run(
            ["docker", "volume", "create", volume_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
