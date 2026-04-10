#!/usr/bin/env python3
"""Run ansible-lint against the project's ansible directory.

Provides a runbook-style entrypoint for editor tasks and CI invocations
that prefer `runbook/quality/*` over direct tool calls.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ansible_lint = shutil.which("ansible-lint") or str(Path(sys.executable).parent / "ansible-lint")
    repo_root = Path(__file__).resolve().parents[2]
    cmd = [ansible_lint, str(repo_root / "ansible")]
    rc = subprocess.run(cmd).returncode
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
