from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(repo_root / "tests"),
        "-p",
        "test_*.py",
    ]

    result = subprocess.run(command, cwd=str(repo_root), check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
