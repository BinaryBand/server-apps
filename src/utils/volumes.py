from pathlib import Path
from typing import List, Optional

from src.utils.secrets import read_secret

# Logical volume names as represented under /data inside the gather container
LOGICAL_VOLUMES = [
	"jellyfin_config",
	"jellyfin_data",
	"baikal_config",
	"baikal_data",
	"minio_data",
]


def docker_volume_name(project: str, logical_name: str) -> str:
	"""Return the docker volume name for a project and logical volume.

	Example: docker_volume_name('cloud', 'jellyfin_data') -> 'cloud_jellyfin_data'
	"""
	return f"{project}_{logical_name}"


def host_bind_path(logical_name: str) -> Optional[Path]:
	"""Return the host override path for a logical volume, if configured.

	Looks for an env var named {LOGICAL_NAME.upper()}_DIR, e.g.
	jellyfin_data -> JELLYFIN_DATA_DIR. Returns the Path only if it exists
	on disk, otherwise None.
	"""
	env_key = logical_name.upper() + "_DIR"
	value = read_secret(env_key)
	if value:
		p = Path(value)
		if p.exists():
			return p
	return None


def rclone_docker_volume_flags(project: str) -> List[str]:
	"""Return docker run volume flags mounting all logical volumes read-only.

	For each volume, if a host path override is configured via env var
	(see host_bind_path), that path is mounted directly instead of the
	named docker volume. This means a bind-mounted service directory is
	picked up automatically without any caller-side wiring.

	Example usage:
	cmd = ["docker", "run", "--rm"]
	cmd += rclone_docker_volume_flags(project)
	"""
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
	"""Return the path under backups where a logical volume would be placed.

	Example: backups_volume_path(Path('.local/backups'), 'jellyfin_data') ->
	Path('.local/backups/volumes/jellyfin_data')
	"""
	return backups_dir / "volumes" / logical_name


def gathered_volume_dirs(backups_dir: Path) -> List[Path]:
	"""Return all volume directories present under backups_dir/volumes/."""
	volumes_root = backups_dir / "volumes"
	if not volumes_root.exists():
		return []
	return sorted(child for child in volumes_root.iterdir() if child.is_dir())

