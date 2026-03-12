from __future__ import annotations

from pathlib import Path
import os
import subprocess
from .ansible_playbook import ansible_playbook_bin
from src.toolbox.core.runtime import repo_root

from typing import Literal


MODE = Literal["bootstrap", "runtime", "reset"]


def run_permissions_playbook(
    *,
    mode: MODE,
    manifest_path: str = "infra/permissions.yml",
    dry_run: bool = False,
) -> None:
    root: Path = repo_root()

    manifest: Path = root / manifest_path
    inventory: Path = root / "ansible" / "inventory.ini"
    playbook: Path = root / "ansible" / "apply-permissions.yml"

    if not playbook.exists():
        raise SystemExit(f"Ansible playbook not found: {playbook}")

    command = [
        ansible_playbook_bin(),
        "-i",
        str(inventory),
        str(playbook),
        "-e",
        f"manifest_path={manifest}",
        "-e",
        f"repo_root={root}",
        "-e",
        f"permissions_mode={mode}",
        "-e",
        f"reset_uid={os.getuid()}",
        "-e",
        f"reset_gid={os.getgid()}",
    ]

    if dry_run:
        command.append("--check")

    if mode == "bootstrap" and os.geteuid() != 0:
        print("Bootstrap mode requires root to apply host ownership/users.")
        subprocess.run(["sudo", *command], check=True)
        return

    subprocess.run(command, check=True, env=os.environ.copy(), cwd=str(repo_root()))


__all__ = ["run_permissions_playbook"]
