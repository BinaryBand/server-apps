from __future__ import annotations

from src.toolbox.docker.post_start.jellyfin import restart_jellyfin
from src.toolbox.docker.post_start.minio import (
    ensure_minio_media_bucket,
    wait_for_minio_ready,
)
from src.toolbox.core.config import minio_credentials


def run_runtime_post_start() -> None:
    restart_jellyfin()
    wait_for_minio_ready()
    # Read required MinIO credentials at this higher application layer
    minio_user, minio_password = minio_credentials()
    ensure_minio_media_bucket(minio_user, minio_password)


__all__ = [
    "restart_jellyfin",
    "wait_for_minio_ready",
    "ensure_minio_media_bucket",
    "run_runtime_post_start",
]
