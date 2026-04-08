from __future__ import annotations

from src.storage.volumes import required_external_volume_names
from src.toolbox.docker.compose_cli import compose_cmd
from src.toolbox.docker.compose_storage import rendered_compose_config, external_alias_name_pairs

import subprocess


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


def _is_runtime_service(service_cfg: object) -> bool:
    if not isinstance(service_cfg, dict):
        return False
    profiles = service_cfg.get("profiles")
    return not isinstance(profiles, list)


def compose_service_names() -> list[str]:
    config = rendered_compose_config()
    services = config.get("services", {})
    return [name for name, service_cfg in services.items() if _is_runtime_service(service_cfg)]


__all__ = [
    "compose_cmd",
    "compose_service_names",
    "ensure_external_volumes",
    "external_alias_name_pairs",
    "missing_external_volumes",
    "probe_external_volume",
    "rendered_compose_config",
    "stop_compose_stack",
]
