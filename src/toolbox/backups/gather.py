from src.toolbox.docker import volumes as volatile
from src.toolbox.docker.wrappers.rclone import rclone_sync

from pathlib import Path


def gather_stage(include_file: Path):
    include_file: Path = include_file.resolve()

    if not include_file.exists():
        raise RuntimeError(f"[gather_stage] Include file not found: {include_file}")

    if not include_file.is_file():
        raise RuntimeError(f"[gather_stage] Include path is not a file: {include_file}")

    docker_args = volatile.rclone_docker_volume_flags()
    docker_args += volatile.storage_docker_mount_flags("backups", "/backups")

    docker_args += ["-v", f"{str(include_file)}:/filters/backup-include.txt:ro"]
    docker_args += volatile.storage_docker_mount_flags(
        "rclone_config", "/config/rclone", read_only=True
    )

    extra_args: list[str] = ["--include-from", "/filters/backup-include.txt"]
    rclone_sync("/data", "/backups", docker_args=docker_args, extra_args=extra_args)


__all__ = ["gather_stage"]
