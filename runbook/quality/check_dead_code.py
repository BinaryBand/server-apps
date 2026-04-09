#!/usr/bin/env python3
"""Run vulture dead-code check via a runbook-style wrapper.

Provides an entrypoint for editor tasks and docs that prefer `runbook/*`.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> None:
    # Use the same python executable used to run this wrapper
    cmd = [sys.executable, "-m", "vulture", "src", "runbook", "--min-confidence", "80"]
    rc = subprocess.run(cmd).returncode
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
