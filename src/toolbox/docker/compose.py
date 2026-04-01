from __future__ import annotations

from src.toolbox.docker.volumes import required_external_volume_names
from src.toolbox.docker.compose_storage import rendered_compose_config
from src.toolbox.core.runtime import repo_root
from src.toolbox.core.config import get_project_name

from pathlib import Path
import subprocess
import dotenv


DOCKER_COMPOSE_CMD: list[str] = ["docker", "compose"]

COMPOSE_FILES: tuple[str, str] = ("compose/base.yml", "compose/dev.yml")


def _compose_file_args() -> list[str]:
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
        file_path = str(root / file)
        cmd += ["-f", file_path]

    return cmd


def compose_cmd(*args: str) -> list[str]:
    return [*DOCKER_COMPOSE_CMD, *_compose_file_args(), *args]


def ensure_external_volumes() -> None:
    try:
        missing = missing_external_volumes()
    except Exception as err:
        print(f"[compose] Failed to determine missing external volumes: {err}")
        return

    for volume_name in missing:
        try:
            subprocess.run(
                ["docker", "volume", "create", volume_name],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            print(f"[compose] Failed to create external volume: {volume_name}")


def missing_external_volumes() -> list[str]:
    missing: list[str] = []
    for volume_name in required_external_volume_names():
        if not probe_external_volume(volume_name):
            missing.append(volume_name)
    return missing


def probe_external_volume(name: str) -> bool:
    try:
        result = subprocess.run(
            ["docker", "volume", "inspect", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False
    return result.returncode == 0


def stop_compose_stack() -> None:
    subprocess.run(compose_cmd("down"), check=True)


def compose_service_names() -> list[str]:
    config = rendered_compose_config()
    return list(config.get("services", {}).keys())


__all__ = [
    "compose_cmd",
    "compose_service_names",
    "ensure_external_volumes",
    "missing_external_volumes",
    "probe_external_volume",
    "stop_compose_stack",
]
