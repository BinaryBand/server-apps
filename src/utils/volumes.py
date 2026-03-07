from pathlib import Path
from typing import List, Optional, Tuple

from src.utils.secrets import read_secret

# Logical volume names as represented under /data inside the gather container
LOGICAL_VOLUMES = [
	"jellyfin_config",
	"jellyfin_data",
	"baikal_config",
	"baikal_data",
	"minio_data",
]

STORAGE_DEFAULT_SUFFIXES = {
	"backups": "backups",
	"restic_repo": "restic",
	"rclone_config": "rclone_config",
}

STORAGE_OVERRIDE_ENV = {
	"backups": "BACKUPS_DIR",
	"restic_repo": "RESTIC_REPO_DIR",
	"rclone_config": "RCLONE_CONFIG_DIR",
}


def docker_volume_name(project: str, logical_name: str) -> str:
	"""Return the docker volume name for a project and logical volume."""
	return f"{project}_{logical_name}"


def host_bind_path(logical_name: str) -> Optional[Path]:
	"""Return the host override path for a logical volume, if configured."""
	env_key = logical_name.upper() + "_DIR"
	value = read_secret(env_key)
	if value:
		p = Path(value).expanduser().resolve()
		if p.exists():
			return p
	return None


def storage_mount_source(project: str, storage_key: str) -> Tuple[str, bool]:
	"""Resolve storage source for docker mounts.

	Returns `(source, is_host_path)` where source is either a host path
	from env override or a named docker volume using project prefix.
	"""
	env_key = STORAGE_OVERRIDE_ENV[storage_key]
	override = read_secret(env_key)
	if override:
		return (str(Path(override).expanduser().resolve()), True)

	suffix = STORAGE_DEFAULT_SUFFIXES[storage_key]
	return (docker_volume_name(project, suffix), False)


def storage_docker_mount_flags(
	project: str,
	storage_key: str,
	target_path: str,
	*,
	read_only: bool = False,
) -> List[str]:
	"""Return docker `-v` flags for storage key with override-aware source."""
	source, is_host = storage_mount_source(project, storage_key)
	if is_host and not read_only:
		Path(source).mkdir(parents=True, exist_ok=True)

	mount = f"{source}:{target_path}"
	if read_only:
		mount += ":ro"
	return ["-v", mount]


def rclone_docker_volume_flags(project: str) -> List[str]:
	"""Return docker run volume flags mounting all logical volumes read-only."""
	flags: List[str] = []
	for logical in LOGICAL_VOLUMES:
		dest = f"/data/volumes/{logical}"
		override = host_bind_path(logical)
		if override:
			flags += ["-v", f"{str(override)}:{dest}:ro"]
		else:
			vol = docker_volume_name(project, logical)
			flags += ["-v", f"{vol}:{dest}:ro"]
	return flags


def backups_volume_path(backups_dir: Path, logical_name: str) -> Path:
	"""Return the path under backups where a logical volume would be placed."""
	return backups_dir / "volumes" / logical_name


def gathered_volume_dirs(backups_dir: Path) -> List[Path]:
	"""Return all volume directories present under backups_dir/volumes/."""
	volumes_root = backups_dir / "volumes"
	if not volumes_root.exists():
		return []
	return sorted(child for child in volumes_root.iterdir() if child.is_dir())

