from dataclasses import dataclass, field

from src.toolbox.core.config import get_project_name
from src.toolbox.docker.volumes_config import storage_docker_mount_flags
from src.toolbox.docker.wrappers.rclone import rclone_sync


_CONSERVATIVE_FLAGS: list[str] = [
    "--transfers", "1",
    "--buffer-size", "64M",
    "--retries", "3",
    "--low-level-retries", "5",
    "--stats", "60s",
]


@dataclass
class RcloneStreamSync:
    """Adapter: stream-sync any rclone source to a remote destination.

    Runs in a disposable container joined to the compose network so that
    service-name endpoints (e.g. http://minio:9000) are reachable.
    """

    source: str
    destination: str
    extra_flags: list[str] = field(default_factory=lambda: list(_CONSERVATIVE_FLAGS))

    def sync(self) -> None:
        docker_args: list[str] = storage_docker_mount_flags(
            "rclone_config", "/config/rclone", read_only=True
        )
        docker_args += ["-e", "RCLONE_CONFIG=/config/rclone/rclone.conf"]
        docker_args += ["--network", f"{get_project_name()}_default"]
        rclone_sync(
            self.source,
            self.destination,
            docker_args=docker_args,
            extra_args=self.extra_flags,
        )


__all__ = ["RcloneStreamSync"]
