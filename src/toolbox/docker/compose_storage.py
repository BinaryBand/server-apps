from __future__ import annotations

from src.configuration.compose_config import ComposeConfigModel
from src.toolbox.runtime import PROJECT_NAME, repo_root

from functools import lru_cache
from pathlib import Path
from typing import Any
import subprocess
import dotenv
import yaml
from pydantic import ValidationError


DOCKER_COMPOSE_CMD: list[str] = ["docker", "compose"]
COMPOSE_FILES: tuple[str, str] = ("compose/base.yml", "compose/dev.yml")


def _compose_file_args() -> list[str]:
    root: Path = repo_root()
    env: str = dotenv.find_dotenv()

    cmd: list[str] = ["--project-name", PROJECT_NAME, "--project-directory", str(root)]

    if env:
        cmd += ["--env-file", env]

    for file in COMPOSE_FILES:
        cmd += ["-f", str(root / file)]

    return cmd


@lru_cache(maxsize=1)
def rendered_compose_config() -> dict[str, Any]:
    cmd: list[str] = [
        *DOCKER_COMPOSE_CMD,
        *_compose_file_args(),
        "config",
        "--no-interpolate",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"[compose_storage] Failed to render: {' '.join(cmd)}\n{proc.stderr.strip()}"
        )

    try:
        data = yaml.safe_load(proc.stdout)
    except Exception as err:
        raise RuntimeError(
            f"[compose_storage] Failed to parse rendered compose YAML: {err}"
        ) from err

    if not isinstance(data, dict):
        raise RuntimeError("[compose_storage] Rendered compose config is not a mapping")

    try:
        model: ComposeConfigModel = ComposeConfigModel.model_validate(data)
    except ValidationError as err:
        raise RuntimeError(
            f"[compose_storage] Rendered compose config failed schema validation: {err}"
        ) from err

    return model.model_dump(mode="python")


def external_alias_name_pairs() -> dict[str, str]:
    config = rendered_compose_config()
    volumes = config.get("volumes")
    if not isinstance(volumes, dict):
        return {}

    pairs: dict[str, str] = {}
    for alias, raw_cfg in volumes.items():
        if not isinstance(alias, str) or not isinstance(raw_cfg, dict):
            continue

        if raw_cfg.get("external") is not True:
            continue

        volume_name = raw_cfg.get("name")
        if isinstance(volume_name, str) and volume_name:
            pairs[alias] = volume_name

    return pairs


def service_volume_sources(service_name: str) -> dict[str, str]:
    config = rendered_compose_config()
    services = config.get("services")
    if not isinstance(services, dict):
        return {}

    service_cfg = services.get(service_name)
    if not isinstance(service_cfg, dict):
        return {}

    volumes = service_cfg.get("volumes")
    if not isinstance(volumes, list):
        return {}

    sources_by_target: dict[str, str] = {}
    for entry in volumes:
        if isinstance(entry, dict):
            source = entry.get("source")
            target = entry.get("target")
            if isinstance(source, str) and isinstance(target, str):
                sources_by_target[target] = source
            continue

        if isinstance(entry, str):
            parts = entry.split(":")
            if len(parts) >= 2 and parts[0] and parts[1]:
                sources_by_target[parts[1]] = parts[0]

    return sources_by_target
