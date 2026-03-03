from __future__ import annotations

from src.utils.secrets import read_secret


COMPOSE_FILES: tuple[str, str] = ("compose/base.yml", "compose/dev.yml")


def compose_base_cmd() -> list[str]:
    compose_cmd = read_secret("DOCKER_COMPOSE_CMD") or "docker compose"
    return compose_cmd.split()


def compose_file_args() -> list[str]:
    return ["-f", COMPOSE_FILES[0], "-f", COMPOSE_FILES[1]]


def compose_cmd(*args: str) -> list[str]:
    return [*compose_base_cmd(), *compose_file_args(), *args]
