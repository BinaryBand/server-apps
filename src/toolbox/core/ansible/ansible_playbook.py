from __future__ import annotations

from pathlib import Path
import shutil
import sys


def ansible_playbook_bin() -> str:
    """Return the path to an `ansible-playbook` binary (virtualenv-aware).

    Intended to be a thin, testable helper separated from the runner logic.
    """
    venv_ansible_playbook = Path(sys.executable).with_name("ansible-playbook")
    if venv_ansible_playbook.exists() and venv_ansible_playbook.is_file():
        return str(venv_ansible_playbook)

    if (ansible_playbook := shutil.which("ansible-playbook")) is not None:
        return ansible_playbook

    raise SystemExit("ansible-playbook is required. Install Ansible and try again.")


__all__ = ["ansible_playbook_bin"]
