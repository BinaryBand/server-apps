from __future__ import annotations

from collections.abc import Callable

from src.observability.health import run_runtime_health_checks
from src.observability.post_start import run_runtime_post_start
from src.orchestrators.setup import ensure_secrets
from src.permissions.ansible import run_permissions_playbook
from src.storage.compose import ensure_external_volumes

PIPELINE_STEPS: list[tuple[str, Callable[[], None]]] = [
    ("setup", lambda: ensure_secrets()),
    ("volumes", lambda: ensure_external_volumes()),
    ("permissions", lambda: run_permissions_playbook(mode="runtime")),
    ("runtime", lambda: run_runtime_post_start()),
    ("health", lambda: run_runtime_health_checks()),
]

__all__ = ["PIPELINE_STEPS"]
