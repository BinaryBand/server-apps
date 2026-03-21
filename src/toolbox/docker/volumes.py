from src.toolbox.docker.compose_storage import (
    external_alias_name_pairs,
    rendered_compose_config,
    service_volume_sources,
)
from src.configuration.storage_manifest import (
    LOGICAL_VOLUME_NAMES,
    STORAGE_TARGETS,
    BIND_MOUNT_ENV,
)
import src.toolbox.core.config as config
from src.toolbox.core.runtime import repo_root

from pathlib import Path
import subprocess


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
    """Return required external docker volume names.

    Names are canonical and defined directly in compose.
    """
    return list(external_alias_name_pairs().values())


def _list_docker_volumes(*args: str) -> list[str]:
    cmd: list[str] = ["docker", "volume", "ls", *args, "--format", "{{.Name}}"]
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        cmd, check=False, capture_output=True, text=True
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def list_project_volumes(project: str) -> list[str]:
    """List compose-managed volumes for this stack."""
    volumes: list[str] = _list_docker_volumes(
        "--filter", f"label=com.docker.compose.project={project}"
    )
    if volumes:
        return volumes

    configured: set[str] = set(external_alias_name_pairs().values())

    compose_volumes = rendered_compose_config().get("volumes")
    if isinstance(compose_volumes, dict):
        for raw_cfg in compose_volumes.values():
            if isinstance(raw_cfg, dict):
                volume_name = raw_cfg.get("name")
                if isinstance(volume_name, str) and volume_name:
                    configured.add(volume_name)

    existing = set(_list_docker_volumes())
    return sorted(name for name in configured if name in existing)


def remove_project_volumes(project: str, *, dry_run: bool = False) -> tuple[int, int]:
    """Remove project volumes and return `(removed, failed)` counters."""
    volumes = list_project_volumes(project)
    if not volumes:
        print("No project volumes found.")
        return 0, 0

    removed = 0
    for volume in volumes:
        if dry_run:
            print(f"Would remove volume: {volume}")
            removed += 1
            continue

        try:
            subprocess.run(["docker", "volume", "rm", "-f", volume], check=True)
            removed += 1
        except subprocess.CalledProcessError:
            print(f"Failed to remove volume: {volume}")

    return (removed, len(volumes) - removed)


def host_bind_path(logical_name: str) -> Path | None:
    """Return host bind path for logical volumes configured as bind mounts."""
    env_key = BIND_MOUNT_ENV.get(logical_name)
    if env_key is None:
        return None

    raw_value = config.bind_mount_value(env_key, "./minio")

    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = repo_root() / path
    return path.resolve()


def logical_volume_mount_source(logical_name: str) -> str:
    """Return the host path or named volume source for a logical app volume."""
    override: Path | None = host_bind_path(logical_name)
    if override is not None:
        return str(override)

    source: str = _logical_source(logical_name)
    return _resolve_volume_source(source)


def storage_mount_source(storage_key: str) -> str:
    """Return the named docker volume backing the requested storage key."""
    source = _storage_source(storage_key)
    return _resolve_volume_source(source)


def storage_docker_mount_flags(
    storage_key: str, target_path: str, *, read_only: bool = False
) -> list[str]:
    """Return docker `-v` flags for a named storage volume."""
    source = storage_mount_source(storage_key)
    mount = f"{source}:{target_path}"
    if read_only:
        mount += ":ro"
    return ["-v", mount]


def rclone_docker_volume_flags() -> list[str]:
    """Return docker run volume flags mounting all logical volumes read-only."""
    flags: list[str] = []
    for logical in logical_volume_names():
        dest = f"/data/volumes/{logical}"
        source: str = logical_volume_mount_source(logical)
        flags += ["-v", f"{source}:{dest}:ro"]
    return flags


__all__ = [
    "logical_volume_names",
    "required_external_volume_names",
    "list_project_volumes",
    "remove_project_volumes",
    "host_bind_path",
    "logical_volume_mount_source",
    "storage_mount_source",
    "storage_docker_mount_flags",
    "rclone_docker_volume_flags",
]
