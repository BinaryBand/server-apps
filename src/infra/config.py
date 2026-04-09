"""Transitional shim: re-export canonical configuration helpers.

The authoritative implementation remains in `src.toolbox.core.config` during
the migration. Keep this shim for callers that import `src.infra.config`.
"""

from src.toolbox.core.config import *  # noqa: F401,F403
