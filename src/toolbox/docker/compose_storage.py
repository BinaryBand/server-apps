from __future__ import annotations

import subprocess
from typing import Any

import yaml
from pydantic import ValidationError

from src.configuration.compose_config import ComposeConfigModel
from src.toolbox.docker.compose_cli import compose_cmd


def _run_compose_config_cmd() -> str:
    """Run docker-compose config command and return rendered YAML."""
    cmd: list[str] = compose_cmd("config", "--no-interpolate")
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"[compose_storage] Failed to render: {' '.join(cmd)}\n{proc.stderr.strip()}"
        )
    return proc.stdout


def rendered_compose_config() -> dict[str, Any]:
    yaml_str = _run_compose_config_cmd()

    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as err:
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


def _extract_external_volume(alias: str, raw_cfg: Any) -> tuple[str, str] | None:
    """Extract external volume alias-name pair or None."""
    if not isinstance(raw_cfg, dict) or raw_cfg.get("external") is not True:
        return None

    volume_name = raw_cfg.get("name")
    if isinstance(volume_name, str) and volume_name:
        return (alias, volume_name)
    return None


def external_alias_name_pairs() -> dict[str, str]:
    config = rendered_compose_config()
    volumes: dict[str, Any] = config.get("volumes", {})

    pairs: dict[str, str] = {}
    for alias, raw_cfg in volumes.items():
        result = _extract_external_volume(alias, raw_cfg)
        if result is not None:
            pairs[result[0]] = result[1]

    return pairs


def _parse_dict_volume_entry(entry: dict) -> tuple[str, str] | None:
    """Extract target and source from dict-form volume config."""
    source = entry.get("source")
    target = entry.get("target")
    if isinstance(source, str) and isinstance(target, str):
        return (target, source)
    return None


def _parse_string_volume_entry(entry: str) -> tuple[str, str] | None:
    """Parse colon-separated source:target string."""
    parts = entry.split(":")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return (parts[1], parts[0])
    return None


def _parse_volume_entry(entry: Any) -> tuple[str, str] | None:
    """Parse a volume entry (dict or string) and return (target, source) or None."""
    if isinstance(entry, dict):
        return _parse_dict_volume_entry(entry)
    if isinstance(entry, str):
        return _parse_string_volume_entry(entry)
    return None


def _get_service_volumes(service_name: str) -> list[Any] | None:
    """Return volume list for a service, or None if not found."""
    config = rendered_compose_config()
    services: dict[str, Any] = config.get("services", {})
    service_cfg = services.get(service_name)
    if not isinstance(service_cfg, dict):
        return None
    volumes = service_cfg.get("volumes")
    return volumes if isinstance(volumes, list) else None


def service_volume_sources(service_name: str) -> dict[str, str]:
    volumes = _get_service_volumes(service_name)
    if volumes is None:
        return {}
    sources_by_target: dict[str, str] = {}
    for entry in volumes:
        result = _parse_volume_entry(entry)
        if result is not None:
            sources_by_target[result[0]] = result[1]
    return sources_by_target


__all__ = [
    "rendered_compose_config",
    "external_alias_name_pairs",
    "service_volume_sources",
]
