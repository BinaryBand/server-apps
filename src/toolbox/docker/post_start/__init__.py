from __future__ import annotations

from src.toolbox.docker.post_start.jellyfin import restart_jellyfin


def run_runtime_post_start() -> None:
    restart_jellyfin()


__all__ = [
    "restart_jellyfin",
    "run_runtime_post_start",
]
