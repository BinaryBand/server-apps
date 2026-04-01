from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
from .ansible_playbook import ansible_playbook_bin
import src.toolbox.core.runtime as runtime

from typing import Literal


MODE = Literal["bootstrap", "runtime", "reset"]


@dataclass(frozen=True)
class _PlaybookPaths:
    root: Path
    manifest: Path
    inventory: Path
    playbook: Path


def _resolve_playbook_paths(manifest_path: str) -> _PlaybookPaths:
    root: Path = runtime.repo_root()
    return _PlaybookPaths(
        root=root,
        manifest=root / manifest_path,
        inventory=root / "ansible" / "inventory.ini",
        playbook=root / "ansible" / "apply-permissions.yml",
    )


def _run_as_sudo(command: list[str]) -> None:
    try:
        subprocess.run(["sudo", *command], check=True)
    except Exception as err:
        raise RuntimeError(
            f"Failed to run permissions playbook via sudo: {err}"
        ) from err


def _build_playbook_command(paths: _PlaybookPaths, *, mode: MODE, dry_run: bool) -> list[str]:
    """Build ansible-playbook command."""
    command = [
        ansible_playbook_bin(),
        "-i",
        str(paths.inventory),
        str(paths.playbook),
        "-e",
        f"manifest_path={paths.manifest}",
        "-e",
        f"repo_root={paths.playbook.parent.parent}",
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


def _run_playbook(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, check=True, env=os.environ.copy(), cwd=str(cwd))


def _run_or_escalate(command: list[str], *, mode: MODE) -> None:
    if mode == "bootstrap" and os.geteuid() != 0:
        print("Bootstrap mode requires root to apply host ownership/users.")
        _run_as_sudo(command)
        return
    _run_playbook(command, cwd=runtime.repo_root())


def run_permissions_playbook(
    *,
    mode: MODE,
    manifest_path: str = "infra/permissions.yml",
    dry_run: bool = False,
) -> None:
    paths = _resolve_playbook_paths(manifest_path)
    if not paths.playbook.exists():
        raise SystemExit(f"Ansible playbook not found: {paths.playbook}")

    command = _build_playbook_command(paths, mode=mode, dry_run=dry_run)

    try:
        _run_or_escalate(command, mode=mode)
    except Exception as err:
        raise RuntimeError(f"Failed to run permissions playbook: {err}") from err


__all__ = ["run_permissions_playbook"]
