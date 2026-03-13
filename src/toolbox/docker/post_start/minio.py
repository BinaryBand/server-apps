from __future__ import annotations

from src.toolbox.docker.health import wait_for_container_health
import subprocess


def wait_for_minio_ready() -> None:
    wait_for_container_health(
        "Wait for MinIO", container="minio", timeout_seconds=60, interval_seconds=2
    )


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


def probe_minio_media_public() -> bool:
    """Return True if the myminio/media bucket has anonymous download access."""
    result = subprocess.run(
        _minio_get_anonymous_command(),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "download" in result.stdout.lower()


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


def ensure_minio_media_bucket(minio_user: str, minio_password: str) -> None:
    """Ensure a media bucket exists in MinIO using provided credentials.

    Credentials MUST be supplied by the caller to keep secret handling at a
    higher level of the application.
    """
    try:
        subprocess.run(_minio_alias_set_command(minio_user, minio_password), check=True)

        stat_result: subprocess.CompletedProcess[bytes] = subprocess.run(
            _minio_stat_media_command(), check=False
        )
        if stat_result.returncode != 0:
            subprocess.run(_minio_create_media_command(), check=True)

        # Always (re)apply the anonymous download policy so the media bucket is
        # publicly readable. Reapplying is idempotent and avoids brittle
        # parsing of `mc anonymous get` output.
        subprocess.run(_minio_set_anonymous_download_command(), check=True)
    except subprocess.CalledProcessError as err:
        raise RuntimeError("failed to ensure MinIO media bucket") from err


__all__ = [
    "wait_for_minio_ready",
    "ensure_minio_media_bucket",
    "probe_minio_media_public",
]
