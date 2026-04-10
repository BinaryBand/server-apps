from __future__ import annotations

from pathlib import Path

import src.infra.config as config
from src.configuration.storage_manifest import (
    BIND_MOUNT_ENV,
    LOGICAL_VOLUME_NAMES,
    STORAGE_TARGETS,
)
from src.infra.docker.compose_storage import (
    external_alias_name_pairs,
    service_volume_sources,
)
from src.infra.runtime import repo_root


def logical_volume_names() -> list[str]:
    return list(LOGICAL_VOLUME_NAMES)


def _resolve_volume_source(source: str) -> str:
    return external_alias_name_pairs().get(source, source)


def _logical_source(logical_name: str) -> str:
    if logical_name not in LOGICAL_VOLUME_NAMES:
        raise KeyError(f"Unknown logical volume: {logical_name}")
    if logical_name not in external_alias_name_pairs().values():
        raise RuntimeError(
            f"[volumes] Logical volume '{logical_name}' not found in compose external volumes"
        )
    return logical_name


def _storage_source(storage_key: str) -> str:
    service_name, target = STORAGE_TARGETS[storage_key]
    source = service_volume_sources(service_name).get(target)
    if source is None:
        raise RuntimeError(
            f"[volumes] Missing source for storage key '{storage_key}' at {service_name}:{target}"
        )
    return source


def required_external_volume_names() -> list[str]:
    return list(external_alias_name_pairs().values())


def host_bind_path(logical_name: str) -> Path | None:
    env_key = BIND_MOUNT_ENV.get(logical_name)
    if env_key is None:
        return None
    raw_value = config.bind_mount_value(env_key, "./minio")
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = repo_root() / path
    return path.resolve()


def logical_volume_mount_source(logical_name: str) -> str:
    override: Path | None = host_bind_path(logical_name)
    if override is not None:
        return str(override)
    source: str = _logical_source(logical_name)
    return _resolve_volume_source(source)


def storage_mount_source(storage_key: str) -> str:
    source = _storage_source(storage_key)
    return _resolve_volume_source(source)


def storage_docker_mount_flags(
    storage_key: str, target_path: str, *, read_only: bool = False
) -> list[str]:
    source = storage_mount_source(storage_key)
    mount = f"{source}:{target_path}"
    if read_only:
        mount += ":ro"
    return ["-v", mount]


def rclone_docker_volume_flags() -> list[str]:
    flags: list[str] = []
    for logical in logical_volume_names():
        dest = f"/data/volumes/{logical}"
        source: str = logical_volume_mount_source(logical)
        flags += ["-v", f"{source}:{dest}:ro"]
    return flags
