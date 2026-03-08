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


def list_project_volumes(project: str) -> list[str]:
    cmd = [
        "docker",
        "volume",
        "ls",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--format",
        "{{.Name}}",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode == 0:
        volumes = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if volumes:
            return volumes

    fallback = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if fallback.returncode != 0:
        return []
    prefix = f"{project}_"
    return [
        line.strip() for line in fallback.stdout.splitlines() if line.startswith(prefix)
    ]


def host_bind_path(logical_name: str) -> Optional[Path]:
    """Return the host override path for logical volumes that still support it."""
    env_key = LOGICAL_VOLUME_OVERRIDE_ENV.get(logical_name)
    if env_key is None:
        return None

    value = read_secret(env_key)
    if value:
        p = Path(value).expanduser().resolve()
        if p.exists():
            return p
    return None


def storage_mount_source(project: str, storage_key: str) -> str:
    """Return the named docker volume backing the requested storage key."""
    suffix = STORAGE_DEFAULT_SUFFIXES[storage_key]
    return docker_volume_name(project, suffix)


def storage_docker_mount_flags(
    project: str,
    storage_key: str,
    target_path: str,
    *,
    read_only: bool = False,
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
        override = host_bind_path(logical)
        if override:
            flags += ["-v", f"{str(override)}:{dest}:ro"]
        else:
            vol = docker_volume_name(project, logical)
            flags += ["-v", f"{vol}:{dest}:ro"]
    return flags
