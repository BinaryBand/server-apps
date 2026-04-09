from __future__ import annotations

from src.storage.compose import (
    compose_cmd,
    compose_service_names,
    ensure_external_volumes,
    external_alias_name_pairs,
    missing_external_volumes,
    probe_external_volume,
    rendered_compose_config,
    stop_compose_stack,
)

"""Compatibility shim: re-export `src.storage.compose` symbols.

Some older code and tests import `src.toolbox.docker.compose`. During the
refactor the canonical implementation lives in `src.storage.compose`; keep this
thin shim so imports remain stable until the migration completes.
"""

__all__ = [
    "compose_cmd",
    "compose_service_names",
    "ensure_external_volumes",
    "external_alias_name_pairs",
    "missing_external_volumes",
    "probe_external_volume",
    "rendered_compose_config",
    "stop_compose_stack",
]
