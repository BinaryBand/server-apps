from src.toolbox.backups.restore import recent_snapshots, restore_snapshot
from src.managers.workflow_runner import StagePolicy, run_checkpoint_stage, start_checkpoint
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.runtime import checkpoints_root, locks_root, repo_root
from src.toolbox.core.config import runbook_resume_enabled

from argparse import ArgumentParser, Namespace
import sys


DEFAULT_RESTORE_TARGET = "/backups/restore"

if __package__ in {None, ""}:
    repo_root_str = str(repo_root())
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def _parse_args() -> Namespace:
    parser = ArgumentParser(description="Restore a restic snapshot")
    parser.add_argument("snapshot", nargs="?", default="latest")
    parser.add_argument("--list-snapshots", action="store_true")
    parser.add_argument("--no-apply-volumes", action="store_true")
    return parser.parse_args()


def _print_snapshots() -> None:
    print("[stage:list] Listing recent snapshots")
    if output := recent_snapshots().strip():
        print(output)
        return
    print("No snapshots found.")


def _run_restore(args: Namespace, *, resume_enabled: bool) -> None:
    checkpoint = start_checkpoint(
        "restore",
        "RestoreCompleted",
        root=checkpoints_root(),
        resume=resume_enabled,
    )

    def _restore_step() -> None:
        restore_snapshot(args.snapshot, DEFAULT_RESTORE_TARGET, args.no_apply_volumes)

    run_checkpoint_stage(
        checkpoint,
        "restore",
        _restore_step,
        StagePolicy(
            observed_on_failure="RestoreFailed",
            run_message="[stage:restore] Starting snapshot restore",
        ),
    )

    checkpoint.finish(observed="RestoreCompleted", ok=True)
    print("[stage:complete] Restore pipeline completed")


def main():
    args = _parse_args()
    resume_enabled = runbook_resume_enabled()

    if args.list_snapshots:
        _print_snapshots()
        return

    with RunbookLock("backup-restore-reset", locks_root()):
        _run_restore(args, resume_enabled=resume_enabled)


if __name__ == "__main__":
    main()
