from src.utils.docker import volumes as volatile
from src.utils.docker.wrappers.rclone import rclone_sync

from pathlib import Path


class GatherError(RuntimeError):
    """Raised when gather operations fail."""


def gather_with_include_file(project: str, include_file: Path):
    include_file = include_file.resolve()

    if not include_file.exists():
        raise GatherError(f"Include file not found: {include_file}")
    if not include_file.is_file():
        raise GatherError(f"Include path is not a file: {include_file}")

    docker_args = volatile.rclone_docker_volume_flags(project)
    docker_args += volatile.storage_docker_mount_flags(project, "backups", "/backups")

    docker_args += ["-v", f"{str(include_file)}:/filters/backup-include.txt:ro"]
    docker_args += volatile.storage_docker_mount_flags(
        project, "rclone_config", "/config/rclone", read_only=True
    )

    try:
        rclone_sync(
            "/data",
            "/backups",
            docker_args=docker_args,
            extra_args=["--include-from", "/filters/backup-include.txt"],
        )
    except Exception as err:
        raise GatherError(err) from err
