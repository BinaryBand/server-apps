"""Compatibility shim: re-export permissions ansible helpers.

This shim keeps the historical import path `src.toolbox.core.ansible` while the
real implementation lives in `src.permissions.ansible`.
"""

from src.permissions.ansible import ansible_playbook_bin, run_permissions_playbook

__all__ = ["ansible_playbook_bin", "run_permissions_playbook"]
