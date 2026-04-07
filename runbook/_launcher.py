from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_orchestrator(orchestrator_name: str) -> int:
    root: Path = Path(__file__).resolve().parents[1]
    orchestrator: Path = root / "src" / "orchestrators" / f"{orchestrator_name}.py"
    cmd = ["poetry", "run", "python", str(orchestrator), *sys.argv[1:]]
    env = {**os.environ, "PYTHONPATH": str(root)}
    return subprocess.run(cmd, env=env).returncode


__all__ = ["run_orchestrator"]
