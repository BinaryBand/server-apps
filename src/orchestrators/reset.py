from src.toolbox.docker.compose import compose_cmd
from src.toolbox.docker.volumes import remove_project_volumes
from src.managers.checkpoint import OperationCheckpoint
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.ansible import run_permissions_playbook
from src.toolbox.core.runtime import (
    checkpoints_root,
    locks_root,
    logs_root,
    media_root,
)
from src.toolbox.core.config import get_project_name

from argparse import ArgumentParser, Namespace
from typing import Literal
from pathlib import Path

import subprocess
import shutil


def remove_local_path(path: Path, *, dry_run: bool = False) -> None:
    if not path.exists():
        return
    action: Literal["Would remove", "Removing"] = (
        "Would remove" if dry_run else "Removing"
    )
    print(f"{action}: {path}")
    if dry_run:
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def normalize_reset_permissions(*, dry_run: bool = False) -> None:
    if dry_run:
        print("Would run: ansible-playbook apply-permissions.yml --check (reset mode)")
        return
    run_permissions_playbook(mode="reset", dry_run=dry_run)


def _print_reset_plan(targets: list[Path], args: Namespace) -> None:
    """Print the planned reset actions."""
    print(f"Project: {get_project_name()}")
    print("This will remove Docker runtime data and local state:")
    print(" - docker compose down --volumes --remove-orphans")
    print(" - project Docker volumes")
    for target in targets:
        print(f" - {target}")


def _confirm_reset() -> bool:
    """Prompt user for reset confirmation. Return True if confirmed."""
    proceed = input("Proceed with clean-slate reset? [y/N]: ").strip().lower()
    return proceed == "y"


def _run_reset_pipeline(checkpoint: OperationCheckpoint, targets: list[Path], args: Namespace) -> None:
    """Execute the reset pipeline stages."""
    compose_down_cmd = compose_cmd("down", "--volumes", "--remove-orphans")
    subprocess.run(compose_down_cmd, check=False)
    checkpoint.mark_stage("compose-down", ok=True)

    removed, failed = remove_project_volumes(
        get_project_name(), dry_run=args.dry_run
    )
    if args.dry_run:
        print(f"Project volumes that would be removed: {removed}, failed: {failed}")
    else:
        print(f"Project volumes removed: {removed}, failed: {failed}")
    checkpoint.mark_stage("remove-volumes", ok=failed == 0)

    if args.dry_run:
        print("Would normalize local reset-path permissions via Ansible...")
    else:
        print("Normalizing local reset-path permissions via Ansible...")
    normalize_reset_permissions(dry_run=args.dry_run)
    checkpoint.mark_stage("reset-permissions", ok=True)

    for target in targets:
        remove_local_path(target, dry_run=args.dry_run)
    checkpoint.mark_stage("cleanup-paths", ok=True)


def _finish_reset(checkpoint: OperationCheckpoint, args: Namespace) -> None:
    """Finish reset and mark completion status."""
    if not args.dry_run:
        if args.keep_media:
            media_root().mkdir(parents=True, exist_ok=True)
        checkpoint.finish(observed="ResetCompleted", ok=True)
        print("Clean slate reset complete.")
    else:
        checkpoint.finish(observed="ResetDryRunCompleted", ok=True)
        print("Dry run complete.")


def main() -> None:
    parser = ArgumentParser(description="Reset project storage and runtime state")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument("--keep-media", action="store_true")
    args: Namespace = parser.parse_args()

    targets: list[Path] = [logs_root()]
    if not args.keep_media:
        targets.append(media_root())

    _print_reset_plan(targets, args)

    if not args.yes:
        if not _confirm_reset():
            print("Aborted.")
            return

    with RunbookLock("backup-restore-reset", locks_root()):
        checkpoint = OperationCheckpoint(
            "reset",
            checkpoints_root(),
            resume=False,
        )
        checkpoint.start(desired="ResetCompleted")

        _run_reset_pipeline(checkpoint, targets, args)
        _finish_reset(checkpoint, args)


if __name__ == "__main__":
    main()
