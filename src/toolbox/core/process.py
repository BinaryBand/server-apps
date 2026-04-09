from __future__ import annotations

import subprocess
from typing import Any, Iterable


def run_process(
    cmd: Iterable[str], *, check: bool = True, **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command from infrastructure/toolbox layer.

    This wrapper centralizes subprocess usage so application code delegates
    execution to an infrastructure implementation (satisfies architecture
    rule requiring adapters/infra to perform external calls).
    """
    return subprocess.run(list(cmd), check=check, **kwargs)
