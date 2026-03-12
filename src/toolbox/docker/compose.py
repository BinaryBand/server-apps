from __future__ import annotations

from src.toolbox.docker.volumes import required_external_volume_names
from src.toolbox.runtime import PROJECT_NAME, repo_root

from pathlib import Path
import subprocess
import dotenv


DOCKER_COMPOSE_CMD: list[str] = ["docker", "compose"]

COMPOSE_FILES: tuple[str, str] = ("compose/base.yml", "compose/dev.yml")


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


def ensure_external_volumes() -> None:
    for volume_name in missing_external_volumes():
        subprocess.run(
            ["docker", "volume", "create", volume_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def missing_external_volumes() -> list[str]:
    missing: list[str] = []
    for volume_name in required_external_volume_names(PROJECT_NAME):
        probe = subprocess.run(
            ["docker", "volume", "inspect", volume_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode != 0:
            missing.append(volume_name)
    return missing
