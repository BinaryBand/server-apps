from __future__ import annotations

from src.utils.runtime import repo_root

import dotenv
import os
import shutil
import subprocess
from typing import Literal


MODE = Literal["bootstrap", "runtime", "reset"]


def _ansible_playbook_bin() -> str:
    if (ansible_playbook := shutil.which("ansible-playbook")) is not None:
        return ansible_playbook

    raise SystemExit("ansible-playbook is required. Install Ansible and try again.")


def run_permissions_playbook(
    *,
    mode: MODE,
    manifest_path: str = "infra/permissions.yml",
    dry_run: bool = False,
) -> None:
    root = repo_root()
    dotenv.load_dotenv()

    manifest = root / manifest_path
    inventory = root / "ansible" / "inventory.ini"
    playbook = root / "ansible" / "apply-permissions.yml"

    if not playbook.exists():
        raise SystemExit(f"Ansible playbook not found: {playbook}")

    command = [
        _ansible_playbook_bin(),
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
