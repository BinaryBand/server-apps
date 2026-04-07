from __future__ import annotations

import subprocess


def restart_jellyfin() -> None:
    try:
        subprocess.run(["docker", "restart", "jellyfin"], check=True)
    except subprocess.CalledProcessError as err:
        raise RuntimeError("failed to restart jellyfin") from err


def run_runtime_post_start() -> None:
    restart_jellyfin()


__all__ = [
    "restart_jellyfin",
    "run_runtime_post_start",
]
