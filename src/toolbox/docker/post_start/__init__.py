from __future__ import annotations

# Shim — canonical implementation moved to src.observability.post_start
from src.observability.post_start import restart_jellyfin, run_runtime_post_start

__all__ = [
    "restart_jellyfin",
    "run_runtime_post_start",
]
