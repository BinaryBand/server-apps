from dataclasses import dataclass, field

from src.storage import volumes as volatile
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

    Logical Docker volumes are always mounted at /data/volumes/<name> so that
    local-path sources (e.g. /data/volumes/jellyfin_data/...) work alongside
    S3-style remotes (e.g. minio:) without any source-type branching.

    The disposable container joins the compose network so that service-name
    endpoints (e.g. http://minio:9000) are reachable.
    """

    source: str
    destination: str
    exclude: list[str] = field(default_factory=list)
    extra_flags: list[str] = field(default_factory=lambda: list(_CONSERVATIVE_FLAGS))

    def _docker_args(self) -> list[str]:
        docker_args: list[str] = volatile.rclone_docker_volume_flags()
        docker_args += storage_docker_mount_flags(
            "rclone_config", "/config/rclone", read_only=True
        )
        docker_args += ["-e", "RCLONE_CONFIG=/config/rclone/rclone.conf"]
        docker_args += ["--network", f"{get_project_name()}_default"]
        return docker_args

    def _effective_flags(self) -> list[str]:
        flags = list(self.extra_flags)
        for pattern in self.exclude:
            flags += ["--exclude", pattern]
        return flags

    def backup(self) -> None:
        rclone_sync(
            self.source,
            self.destination,
            docker_args=self._docker_args(),
            extra_args=self._effective_flags(),
        )

    def restore(self) -> None:
        rclone_sync(
            self.destination,
            self.source,
            docker_args=self._docker_args(),
            extra_args=self._effective_flags(),
        )


__all__ = ["RcloneStreamSync"]
