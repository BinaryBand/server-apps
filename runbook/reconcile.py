import os
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root: Path = Path(__file__).resolve().parents[1]
    orchestrator: Path = root / "src" / "orchestrators" / "reconcile.py"
    sys.exit(
        subprocess.run(
            [sys.executable, str(orchestrator), *sys.argv[1:]],
            env={**os.environ, "PYTHONPATH": str(root)},
        ).returncode
    )
