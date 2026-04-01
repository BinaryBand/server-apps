from __future__ import annotations

import subprocess


def _minio_stat_media_command() -> list[str]:
    return ["docker", "exec", "minio", "mc", "stat", "myminio/media"]


def probe_minio_media_public() -> bool:
    """Return True if the myminio/media bucket has anonymous download access."""
    result = subprocess.run(
        _minio_stat_media_command(),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "anonymous: enabled" in result.stdout.lower()


__all__ = [
    "probe_minio_media_public",
]
