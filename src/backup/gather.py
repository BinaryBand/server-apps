from src.storage import volumes as volatile
from src.toolbox.docker.wrappers.rclone import rclone_sync

from collections.abc import Sequence


def gather_stage(include: Sequence[str], exclude: Sequence[str] = ()) -> None:
    docker_args = volatile.rclone_docker_volume_flags()
    docker_args += volatile.storage_docker_mount_flags("backups", "/backups")
    docker_args += volatile.storage_docker_mount_flags(
        "rclone_config", "/config/rclone", read_only=True
    )

    extra_args: list[str] = []
    for pattern in include:
        extra_args += ["--include", pattern]
    for pattern in exclude:
        extra_args += ["--exclude", pattern]

    rclone_sync("/data", "/backups", docker_args=docker_args, extra_args=extra_args)


__all__ = ["gather_stage"]
