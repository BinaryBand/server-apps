from src.toolbox.backups.restore import recent_snapshots, restore_snapshot
from src.managers.checkpoint import OperationCheckpoint
from src.toolbox.locking import RunbookLock
from src.toolbox.runtime import checkpoints_root, locks_root, repo_root

from argparse import ArgumentParser, Namespace
import os
import sys


DEFAULT_RESTORE_TARGET = "/backups/restore"

if __package__ in {None, ""}:
    repo_root_str = str(repo_root())
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def main():
    parser = ArgumentParser(description="Restore a restic snapshot")
    parser.add_argument("snapshot", nargs="?", default="latest")
    parser.add_argument("--list-snapshots", action="store_true")
    parser.add_argument("--no-apply-volumes", action="store_true")
    args: Namespace = parser.parse_args()
    resume_enabled = os.getenv("RUNBOOK_RESUME", "0") in {"1", "true", "True", "yes"}

    if args.list_snapshots:
        print("[stage:list] Listing recent snapshots")
        if output := recent_snapshots().strip():
            print(output)
        else:
            print("No snapshots found.")
        return

    with RunbookLock("backup-restore-reset", locks_root()):
        checkpoint = OperationCheckpoint(
            "restore",
            checkpoints_root(),
            resume=resume_enabled,
        )
        checkpoint.start(desired="RestoreCompleted")

        try:
            if checkpoint.should_skip_stage("restore"):
                print("[stage:restore] Skipping already completed stage")
            else:
                print("[stage:restore] Starting snapshot restore")
                restore_snapshot(
                    args.snapshot, DEFAULT_RESTORE_TARGET, args.no_apply_volumes
                )
                checkpoint.mark_stage("restore", ok=True)

            checkpoint.finish(observed="RestoreCompleted", ok=True)
            print("[stage:complete] Restore pipeline completed")
        except RuntimeError as err:
            checkpoint.mark_stage("restore", ok=False, message=str(err))
            checkpoint.finish(observed="RestoreFailed", ok=False)
            raise SystemExit(f"[stage:restore] {err}") from err


if __name__ == "__main__":
    main()
