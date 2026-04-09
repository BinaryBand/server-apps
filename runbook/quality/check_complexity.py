#!/usr/bin/env python3
"""Run the project's canonical complexity file-gate wrapper.

This wrapper exists to provide a `runbook/`-style entrypoint for editor
tasks and old docs referencing `runbook/quality/*`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "quality" / "lizard_file_gate.py"
    cmd = [
        sys.executable,
        str(script),
        "src",
        "runbook",
        "--max-file-ccn-sum",
        "35",
        "--max-file-avg-ccn",
        "4.5",
        "--max-file-high-risk-funcs",
        "2",
        "--high-risk-ccn",
        "6",
    ]
    rc = subprocess.run(cmd).returncode
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
