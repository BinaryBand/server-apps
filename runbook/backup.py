import os
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root: Path = Path(__file__).resolve().parents[1]
    orchestrator: Path = root / "src" / "orchestrators" / "backup.py"
    cmd = ["poetry", "run", "python", str(orchestrator), *sys.argv[1:]]
    env = {**os.environ, "PYTHONPATH": str(root)}
    sys.exit(subprocess.run(cmd, env=env).returncode)
