from __future__ import annotations

from src.toolbox.docker.health import wait_for_container_health
from src.toolbox.core.secrets import read_secret

import subprocess


def _require_secret(name: str, fallback_name: str | None = None) -> str:
    value = read_secret(name)
    if not value and fallback_name is not None:
        value = read_secret(fallback_name)

    if not value:
        if fallback_name is not None:
            raise RuntimeError(f"missing required secret: {name} (or {fallback_name})")
        raise RuntimeError(f"missing required secret: {name}")

    return value


def wait_for_minio_ready() -> None:
    try:
        wait_for_container_health(
            "Wait for MinIO", container="minio", timeout_seconds=60, interval_seconds=2
        )
    except RuntimeError as err:
        raise RuntimeError(str(err)) from err


def _minio_alias_set_command(user: str, password: str) -> list[str]:
    return [
        "docker",
        "exec",
        "minio",
        "mc",
        "alias",
        "set",
        "myminio",
        "http://127.0.0.1:9000",
        user,
        password,
    ]


def _minio_stat_media_command() -> list[str]:
    return ["docker", "exec", "minio", "mc", "stat", "myminio/media"]


def _minio_create_media_command() -> list[str]:
    return ["docker", "exec", "minio", "mc", "mb", "myminio/media"]


def _minio_get_anonymous_command() -> list[str]:
    return ["docker", "exec", "minio", "mc", "anonymous", "get", "myminio/media"]


def _minio_set_anonymous_download_command() -> list[str]:
    return [
        "docker",
        "exec",
        "minio",
        "mc",
        "anonymous",
        "set",
        "download",
        "myminio/media",
    ]


def ensure_minio_media_bucket() -> None:
    minio_user: str = _require_secret("MINIO_ROOT_USER", "S3_ACCESS_KEY")
    minio_password: str = _require_secret("MINIO_ROOT_PASSWORD", "S3_SECRET_KEY")

    try:
        subprocess.run(_minio_alias_set_command(minio_user, minio_password), check=True)

        stat_result: subprocess.CompletedProcess[bytes] = subprocess.run(
            _minio_stat_media_command(), check=False
        )
        if stat_result.returncode != 0:
            subprocess.run(_minio_create_media_command(), check=True)

        anonymous_result: subprocess.CompletedProcess[str] = subprocess.run(
            _minio_get_anonymous_command(),
            check=False,
            capture_output=True,
            text=True,
        )

        if "download" not in anonymous_result.stdout.lower():
            subprocess.run(_minio_set_anonymous_download_command(), check=True)
    except subprocess.CalledProcessError as err:
        raise RuntimeError("failed to ensure MinIO media bucket") from err


__all__ = [
    "wait_for_minio_ready",
    "ensure_minio_media_bucket",
]
