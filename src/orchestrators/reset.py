from __future__ import annotations

import argparse

from src.storage.volumes import remove_project_volumes
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.process import run_process
from src.toolbox.core.runtime import PROJECT_NAME, locks_root
from src.toolbox.docker.compose import compose_cmd


def _confirm_reset() -> bool:
    resp = input("This will remove project volumes and reset state. Type 'yes' to continue: ")
    return resp.strip().lower() == "yes"


def normalize_reset_permissions() -> None:
    """Normalize permissions after reset. Placeholder for platform-specific logic."""
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset environment to a clean state")
    parser.add_argument("--yes", action="store_true", dest="yes")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    args = parser.parse_args()

    if not args.yes:
        if not _confirm_reset():
            print("Reset aborted by user")
            return

    with RunbookLock("reset", locks_root()):
        # bring down compose-managed services
        cmd = compose_cmd()
        if not args.dry_run:
            run_process(cmd, check=True)
        else:
            print("Dry run: would run:", cmd)

        # remove volumes for this project
        removed, failed = remove_project_volumes(PROJECT_NAME, dry_run=args.dry_run)
        print(f"Removed {removed} volumes, {failed} failures")

        # normalize permissions if required
        normalize_reset_permissions()


__all__ = [
    "main",
    "_confirm_reset",
    "remove_project_volumes",
    "normalize_reset_permissions",
    "compose_cmd",
]
