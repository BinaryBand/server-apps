from __future__ import annotations

from pathlib import Path

import dotenv

from src.toolbox.core.config import get_project_name
from src.toolbox.core.runtime import repo_root

DOCKER_COMPOSE_CMD: list[str] = ["docker", "compose"]
COMPOSE_FILES: tuple[str, str] = ("compose/base.yml", "compose/dev.yml")


def compose_file_args() -> list[str]:
    root: Path = repo_root()
    env: str = dotenv.find_dotenv()

    cmd: list[str] = [
        "--project-name",
        get_project_name(),
        "--project-directory",
        str(root),
    ]

    if env:
        cmd += ["--env-file", env]

    for file in COMPOSE_FILES:
        cmd += ["-f", str(root / file)]

    return cmd


def compose_cmd(*args: str) -> list[str]:
    return [*DOCKER_COMPOSE_CMD, *compose_file_args(), *args]


__all__ = ["compose_cmd", "compose_file_args"]
