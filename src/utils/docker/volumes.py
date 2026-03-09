from src.utils.secrets import read_secret

from pathlib import Path
from typing import Optional
import subprocess


# Logical volume names as represented under /data inside the gather container
LOGICAL_VOLUMES: list[str] = [
    "jellyfin_config",
    "jellyfin_data",
    "baikal_config",
    "baikal_data",
    "minio_data",
]

STORAGE_DEFAULT_SUFFIXES: dict[str, str] = {
    "backups": "backups_data",
    "restic_repo": "restic_repo_data",
    "rclone_config": "rclone_config",
}

LOGICAL_VOLUME_OVERRIDE_ENV: dict[str, str] = {
    "minio_data": "MINIO_DATA_DIR",
}


def docker_volume_name(project: str, logical_name: str) -> str:
    """Return the docker volume name for a project and logical volume."""
    return f"{project}_{logical_name}"


def _list_docker_volumes(*args: str) -> list[str]:
    cmd = ["docker", "volume", "ls", *args, "--format", "{{.Name}}"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def list_project_volumes(project: str) -> list[str]:
    """List project-owned volumes, preferring compose labels with a prefix fallback."""
    volumes = _list_docker_volumes(
        "--filter", f"label=com.docker.compose.project={project}"
    )
    if volumes:
        return volumes

    fallback = _list_docker_volumes()
    prefix = f"{project}_"
    return [name for name in fallback if name.startswith(prefix)]


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


def host_bind_path(logical_name: str) -> Optional[Path]:
    """Return the host override path for logical volumes that still support it."""
    env_key = LOGICAL_VOLUME_OVERRIDE_ENV.get(logical_name)
    if env_key is None:
        return None

    if value := read_secret(env_key):
        p = Path(value).expanduser().resolve()
        if p.exists():
            return p
    return None


def logical_volume_mount_source(project: str, logical_name: str) -> str:
    """Return the host path or named volume source for a logical app volume."""
    override = host_bind_path(logical_name)
    if override is not None:
        return str(override)
    return docker_volume_name(project, logical_name)


def storage_mount_source(project: str, storage_key: str) -> str:
    """Return the named docker volume backing the requested storage key."""
    suffix = STORAGE_DEFAULT_SUFFIXES[storage_key]
    return docker_volume_name(project, suffix)


def storage_docker_mount_flags(
    project: str, storage_key: str, target_path: str, *, read_only: bool = False
) -> list[str]:
    """Return docker `-v` flags for a named storage volume."""
    source = storage_mount_source(project, storage_key)
    mount = f"{source}:{target_path}"
    if read_only:
        mount += ":ro"
    return ["-v", mount]


def rclone_docker_volume_flags(project: str) -> list[str]:
    """Return docker run volume flags mounting all logical volumes read-only."""
    flags: list[str] = []
    for logical in LOGICAL_VOLUMES:
        dest = f"/data/volumes/{logical}"
        source = logical_volume_mount_source(project, logical)
        flags += ["-v", f"{source}:{dest}:ro"]
    return flags
