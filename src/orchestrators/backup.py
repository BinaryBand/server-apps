from src.toolbox.backups.gather import gather_stage
from src.managers.checkpoint import OperationCheckpoint
from src.toolbox.docker.wrappers.restic import (
    ResticRunnerError,
    has_restic_repo,
    init_restic_repo,
    run_backup,
)
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.runtime import (
    checkpoints_root,
    locks_root,
    repo_root,
)

from pathlib import Path
import sys
from src.toolbox.core.config import runbook_resume_enabled

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root()))


DEFAULT_RESTIC_EXCLUDES: list[str] = ["/backups/restore/**"]
DEFAULT_RESTIC_TARGET = "/backups"


def _run_gather_stage(checkpoint: OperationCheckpoint, include_file: Path) -> None:
    """Run gather stage and mark checkpoint."""
    if checkpoint.should_skip_stage("gather"):
        print("[stage:gather] Skipping already completed stage")
        return

    try:
        print("[stage:gather] Starting gather phase")
        gather_stage(include_file=include_file)
        checkpoint.mark_stage("gather", ok=True)
    except RuntimeError as err:
        checkpoint.mark_stage("gather", ok=False, message=str(err))
        checkpoint.finish(observed="BackupFailed", ok=False)
        raise SystemExit(f"[stage:gather] {err}") from err


def _run_restic_stage(checkpoint: OperationCheckpoint, restic_args: list[str]) -> None:
    """Run restic stage and mark checkpoint."""
    if checkpoint.should_skip_stage("restic"):
        print("[stage:restic] Skipping already completed stage")
        return

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


def main():
    resume_enabled = runbook_resume_enabled()

    with RunbookLock("backup-restore-reset", locks_root()):
        checkpoint = OperationCheckpoint(
            "backup", checkpoints_root(), resume=resume_enabled
        )
        checkpoint.start(desired="BackupCompleted")

        root: Path = repo_root()
        include_file: Path = root / "configs" / "backup-include.txt"

        _run_gather_stage(checkpoint, include_file)

        restic_args = []
        if DEFAULT_RESTIC_TARGET == "/backups":
            for pattern in DEFAULT_RESTIC_EXCLUDES:
                restic_args.extend(["--exclude", pattern])

        _run_restic_stage(checkpoint, restic_args)

        checkpoint.finish(observed="BackupCompleted", ok=True)
        print("[stage:complete] Backup pipeline completed")


if __name__ == "__main__":
    main()
