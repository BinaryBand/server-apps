from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import sys

import src.toolbox.core.runtime as runtime

from typing import Literal


MODE = Literal["bootstrap", "runtime", "reset"]


@dataclass(frozen=True)
class _PlaybookPaths:
	root: Path
	manifest: Path
	inventory: Path
	playbook: Path


def ansible_playbook_bin() -> str:
	"""Return the path to an `ansible-playbook` binary (virtualenv-aware)."""
	venv_ansible_playbook = Path(sys.executable).with_name("ansible-playbook")
	if venv_ansible_playbook.exists() and venv_ansible_playbook.is_file():
		return str(venv_ansible_playbook)

	if (ansible_playbook := shutil.which("ansible-playbook")) is not None:
		return ansible_playbook

	raise SystemExit("ansible-playbook is required. Install Ansible and try again.")


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


def _build_recovery_playbook_command(
	paths: _PlaybookPaths,
	*,
	mode: MODE,
	dry_run: bool,
) -> list[str]:
	command = _build_playbook_command(paths, mode=mode, dry_run=dry_run)
	command.extend([
		"--ask-become-pass",
		"-e",
		"runtime_recover_with_become_request=true",
	])
	return command


def _run_playbook(command: list[str], *, cwd: Path) -> None:
	subprocess.run(command, check=True, env=os.environ.copy(), cwd=str(cwd))


def _format_runtime_failure_hint(err: Exception, *, mode: MODE) -> str:
	if mode != "runtime":
		return str(err)

	lowered = str(err).lower()
	if "permission denied" in lowered and "docker.sock" in lowered:
		return (
			f"{err}. Runtime mode requires Docker daemon access for compose/docker tasks. "
			"Grant current user access to /var/run/docker.sock (for example via docker group), "
			"start a new shell/session, then retry start/reconcile."
		)
	return str(err)


def _run_or_escalate(command: list[str], *, mode: MODE) -> None:
	if mode == "bootstrap" and os.geteuid() != 0:
		print("Bootstrap mode requires root to apply host ownership/users.")
		_run_as_sudo(command)
		return
	_run_playbook(command, cwd=runtime.repo_root())


def run_permissions_playbook(
	*,
	mode: MODE,
	manifest_path: str = "ansible/permissions.yml",
	dry_run: bool = False,
) -> None:
	paths = _resolve_playbook_paths(manifest_path)
	if not paths.playbook.exists():
		raise SystemExit(f"Ansible playbook not found: {paths.playbook}")

	command = _build_playbook_command(paths, mode=mode, dry_run=dry_run)

	try:
		_run_or_escalate(command, mode=mode)
	except Exception as err:
		if mode == "runtime" and not dry_run:
			print(
				"[permissions] Runtime playbook failed; retrying with sudo prompt for recovery tasks..."
			)
			recovery_cmd = _build_recovery_playbook_command(
				paths,
				mode=mode,
				dry_run=dry_run,
			)
			try:
				_run_playbook(recovery_cmd, cwd=runtime.repo_root())
				return
			except Exception as retry_err:
				hint = _format_runtime_failure_hint(retry_err, mode=mode)
				raise RuntimeError(f"Failed to run permissions playbook: {hint}") from retry_err

		hint = _format_runtime_failure_hint(err, mode=mode)
		raise RuntimeError(f"Failed to run permissions playbook: {hint}") from err


__all__ = ["ansible_playbook_bin", "run_permissions_playbook"]
