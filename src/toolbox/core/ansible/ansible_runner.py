from __future__ import annotations

from pathlib import Path
import os
import subprocess
from .ansible_playbook import ansible_playbook_bin
import src.toolbox.core.runtime as runtime

from typing import Literal


MODE = Literal["bootstrap", "runtime", "reset"]


def _build_playbook_command(
    mode: MODE, manifest: Path, inventory: Path, playbook: Path, dry_run: bool
) -> list[str]:
    """Build ansible-playbook command."""
    command = [
        ansible_playbook_bin(),
        "-i",
        str(inventory),
        str(playbook),
        "-e",
        f"manifest_path={manifest}",
        "-e",
        f"repo_root={playbook.parent.parent}",
        "-e",
        f"permissions_mode={mode}",
        "-e",
        f"reset_uid={os.getuid()}",
        "-e",
        f"reset_gid={os.getgid()}",
    ]
    if dry_run:
        command.append("--check")
    return command


def run_permissions_playbook(
    *,
    mode: MODE,
    manifest_path: str = "infra/permissions.yml",
    dry_run: bool = False,
) -> None:
    root: Path = runtime.repo_root()

    manifest: Path = root / manifest_path
    inventory: Path = root / "ansible" / "inventory.ini"
    playbook: Path = root / "ansible" / "apply-permissions.yml"

    if not playbook.exists():
        raise SystemExit(f"Ansible playbook not found: {playbook}")

    command = _build_playbook_command(mode, manifest, inventory, playbook, dry_run)

    if mode == "bootstrap" and os.geteuid() != 0:
        print("Bootstrap mode requires root to apply host ownership/users.")
        _run_as_sudo(command)
        return

    try:
        subprocess.run(command, check=True, env=os.environ.copy(), cwd=str(root))
    except Exception as err:
        raise RuntimeError(f"Failed to run permissions playbook: {err}") from err


__all__ = ["run_permissions_playbook"]
