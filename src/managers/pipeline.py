from __future__ import annotations

from src.toolbox.docker.compose import ensure_external_volumes
from src.toolbox.core.ansible import run_permissions_playbook
from src.toolbox.docker.post_start import run_runtime_post_start
from src.toolbox.docker.health import run_runtime_health_checks
from src.orchestrators.sync_media import sync_media

from collections.abc import Callable


def run_media_sync() -> None:
    """Best-effort media refresh from rclone mount to read volume.

    This must not block startup in environments where the remote mount is
    unavailable or still warming up.
    """
    try:
        sync_media(dry_run=False, delete=False)
    except RuntimeError as err:
        print(f"[pipeline] media sync skipped: {err}")


PIPELINE_STEPS: list[tuple[str, Callable[[], None]]] = [
    ("volumes", lambda: ensure_external_volumes()),
    ("permissions", lambda: run_permissions_playbook(mode="runtime")),
    ("runtime", lambda: run_runtime_post_start()),
    ("media-sync", run_media_sync),
    ("health", lambda: run_runtime_health_checks()),
]

__all__ = ["PIPELINE_STEPS"]
