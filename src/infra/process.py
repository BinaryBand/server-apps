from __future__ import annotations

import subprocess
from typing import Any, Iterable


def run_process(
    cmd: Iterable[str], *, check: bool = True, **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command from the infrastructure layer."""
    return subprocess.run(list(cmd), check=check, **kwargs)
