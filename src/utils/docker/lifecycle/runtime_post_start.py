from __future__ import annotations

from src.utils.docker.post_start.jellyfin import restart_jellyfin
from src.utils.docker.post_start.minio import (
    ensure_minio_media_bucket,
    wait_for_minio_ready,
)


def run_runtime_post_start() -> None:
    restart_jellyfin()
    wait_for_minio_ready()
    ensure_minio_media_bucket()


__all__ = [
    "restart_jellyfin",
    "wait_for_minio_ready",
    "ensure_minio_media_bucket",
    "run_runtime_post_start",
]
