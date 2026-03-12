from src.toolbox.backups.gather import gather_stage
from src.managers.checkpoint import OperationCheckpoint
from src.toolbox.docker.wrappers.restic import (
    ResticRunnerError,
    has_restic_repo,
    init_restic_repo,
    run_backup,
)
from src.toolbox.locking import RunbookLock
from src.toolbox.runtime import PROJECT_NAME, checkpoints_root, locks_root, repo_root

from pathlib import Path
import sys
import os

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root()))


DEFAULT_RESTIC_EXCLUDES: list[str] = ["/backups/restore/**"]
DEFAULT_RESTIC_TARGET = "/backups"


def main():
    resume_enabled = os.getenv("RUNBOOK_RESUME", "0") in {"1", "true", "True", "yes"}

    with RunbookLock("backup-restore-reset", locks_root()):
        checkpoint = OperationCheckpoint(
            "backup", checkpoints_root(), resume=resume_enabled
        )
        checkpoint.start(desired="BackupCompleted")

        root: Path = repo_root()
        include_file = root / "configs" / "backup-include.txt"

        if checkpoint.should_skip_stage("gather"):
            print("[stage:gather] Skipping already completed stage")
        else:
            try:
                print("[stage:gather] Starting gather phase")
                gather_stage(project=PROJECT_NAME, include_file=include_file)
                checkpoint.mark_stage("gather", ok=True)
            except RuntimeError as err:
                checkpoint.mark_stage("gather", ok=False, message=str(err))
                checkpoint.finish(observed="BackupFailed", ok=False)
                raise SystemExit(f"[stage:gather] {err}") from err

        restic_args = []
        if DEFAULT_RESTIC_TARGET == "/backups":
            for pattern in DEFAULT_RESTIC_EXCLUDES:
                restic_args.extend(["--exclude", pattern])

        if checkpoint.should_skip_stage("restic"):
            print("[stage:restic] Skipping already completed stage")
        else:
            print("[stage:restic] Checking repository state")
            if not has_restic_repo():
                print("[stage:restic-init] Repository not initialized; running init")
                try:
                    init_restic_repo()
                except ResticRunnerError as err:
                    checkpoint.mark_stage("restic", ok=False, message=str(err))
                    checkpoint.finish(observed="BackupFailed", ok=False)
                    raise SystemExit(f"[stage:restic-init] {err}") from err

            try:
                run_backup(paths=[DEFAULT_RESTIC_TARGET], args=restic_args)
                checkpoint.mark_stage("restic", ok=True)
            except ResticRunnerError as err:
                checkpoint.mark_stage("restic", ok=False, message=str(err))
                checkpoint.finish(observed="BackupFailed", ok=False)
                raise SystemExit(f"[stage:restic-backup] {err}") from err

        checkpoint.finish(observed="BackupCompleted", ok=True)
        print("[stage:complete] Backup pipeline completed")


if __name__ == "__main__":
    main()
