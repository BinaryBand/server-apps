from __future__ import annotations

from src.toolbox.docker.compose import ensure_external_volumes
from src.toolbox.core.ansible import run_permissions_playbook
from src.toolbox.docker.post_start import run_runtime_post_start
from src.toolbox.docker.health import run_runtime_health_checks
from src.toolbox.core.secrets import read_secret

import sys
import subprocess

from collections.abc import Callable

def _pcloud_preflight() -> None:
    token = read_secret("PCLOUD_ACCESS_TOKEN")
    if token:
        return

    # If interactive, offer to run the helper; otherwise print instructions.
    if sys.stdin.isatty():
        print("PCLOUD_ACCESS_TOKEN not found. To obtain one, run: python runbook/authorize_rclone.py --install-volume")
        try:
            ans = input("Run the interactive helper now? (y/N): ").strip().lower()
        except EOFError:
            ans = "n"
        if ans == "y":
            subprocess.run([sys.executable, "runbook/authorize_rclone.py", "--install-volume"], check=False)
    else:
        print("PCLOUD_ACCESS_TOKEN missing. For headless servers, inject the token via environment or use the authorize helper from another machine.")


PIPELINE_STEPS: list[tuple[str, Callable[[], None]]] = [
    ("preflight", lambda: _pcloud_preflight()),
    ("volumes", lambda: ensure_external_volumes()),
    ("permissions", lambda: run_permissions_playbook(mode="runtime")),
    ("runtime", lambda: run_runtime_post_start()),
    ("health", lambda: run_runtime_health_checks()),
]

__all__ = ["PIPELINE_STEPS"]
