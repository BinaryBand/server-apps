from __future__ import annotations

"""Compatibility shim re-exports for ansible permissions utilities.

Older import sites reference `src.toolbox.core.ansible`. During the
refactor the canonical implementation moved to `src.permissions.ansible`.
Keep this thin shim to preserve imports for tests and downstream callers.
"""

from src.permissions.ansible import ansible_playbook_bin, run_permissions_playbook

__all__ = ["run_permissions_playbook", "ansible_playbook_bin"]
