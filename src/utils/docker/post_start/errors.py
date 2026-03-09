from __future__ import annotations


class RuntimePostStartError(RuntimeError):
    """Raised when post-start runtime setup actions fail."""
