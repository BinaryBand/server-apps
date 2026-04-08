from src.backup.gather import gather_stage
from src.backup.stage_runner import run_backup_stage
from src.adapters.rclone.stream_sync import RcloneStreamSync
from src.adapters.rclone.compress_stage import CompressStage
from src.configuration.backup_config import BackupConfig
from src.workflows.checkpoint import OperationCheckpoint
from src.workflows.workflow_runner import (
    StagePolicy,
    fail_checkpoint_stage,
    run_checkpoint_stage,
    start_checkpoint,
)
from src.backup.restic import (
    ResticRunnerError,
    has_restic_repo,
    init_restic_repo,
    run_backup,
    push_restic_to_cloud,
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
from src.toolbox.core.config import restic_pcloud_sync_enabled

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root()))


DEFAULT_RESTIC_EXCLUDES: list[str] = ["/backups/restore/**"]
DEFAULT_RESTIC_TARGET = "/backups"


def _build_restic_args() -> list[str]:
    restic_args: list[str] = []
    if DEFAULT_RESTIC_TARGET == "/backups":
        for pattern in DEFAULT_RESTIC_EXCLUDES:
            restic_args.extend(["--exclude", pattern])
    return restic_args


def _ensure_restic_repo(checkpoint: OperationCheckpoint) -> None:
    if has_restic_repo():
        return

    print("[stage:restic-init] Repository not initialized; running init")
    try:
        init_restic_repo()
    except ResticRunnerError as err:
        fail_checkpoint_stage(
            checkpoint,
            "restic",
            err=err,
            policy=StagePolicy(
                observed_on_failure="BackupFailed",
                error_prefix="restic-init",
            ),
        )


def _run_restic_backup(checkpoint: OperationCheckpoint, restic_args: list[str]) -> None:
    try:
        run_backup(paths=[DEFAULT_RESTIC_TARGET], args=restic_args)
        checkpoint.mark_stage("restic", ok=True)
    except ResticRunnerError as err:
        fail_checkpoint_stage(
            checkpoint,
            "restic",
            err=err,
            policy=StagePolicy(
                observed_on_failure="BackupFailed",
                error_prefix="restic-backup",
            ),
        )


def _run_restic_stage(checkpoint: OperationCheckpoint, restic_args: list[str]) -> None:
    """Run restic stage and mark checkpoint."""
    if checkpoint.should_skip_stage("restic"):
        print("[stage:restic] Skipping already completed stage")
        return

    print("[stage:restic] Checking repository state")
    _ensure_restic_repo(checkpoint)
    _run_restic_backup(checkpoint, restic_args)


def _run_backup_stages(checkpoint: OperationCheckpoint, config: BackupConfig) -> None:
    run_checkpoint_stage(
        checkpoint,
        "gather",
        lambda: gather_stage(config.batch.include, config.batch.exclude),
        StagePolicy(
            observed_on_failure="BackupFailed",
            run_message="[stage:gather] Starting gather phase",
        ),
    )
    _run_restic_stage(checkpoint, _build_restic_args())

    for source in config.stream:
        stage = RcloneStreamSync(
            source=source.source,
            destination=source.destination,
            exclude=source.exclude,
        )
        run_checkpoint_stage(
            checkpoint,
            f"stream-{source.name}",
            lambda s=stage, n=source.name: run_backup_stage(s, n),
            StagePolicy(
                observed_on_failure="BackupFailed",
                run_message=f"[stage:stream-{source.name}] Syncing {source.source} to {source.destination}",
            ),
        )

    for source in config.compress:
        stage = CompressStage(config=source)
        run_checkpoint_stage(
            checkpoint,
            f"compress-{source.name}",
            lambda s=stage, n=source.name: run_backup_stage(s, n),
            StagePolicy(
                observed_on_failure="BackupFailed",
                run_message=f"[stage:compress-{source.name}] Compressing {source.source} to {source.destination}",
            ),
        )


def main():
    resume_enabled = runbook_resume_enabled()
    root: Path = repo_root()
    config = BackupConfig.from_toml(root / "configs" / "backup.toml")

    with RunbookLock("backup-restore-reset", locks_root()):
        checkpoint = start_checkpoint(
            "backup",
            "BackupCompleted",
            root=checkpoints_root(),
            resume=resume_enabled,
        )
        _run_backup_stages(checkpoint, config)

        checkpoint.finish(observed="BackupCompleted", ok=True)
        # Optionally push the restic repository offsite to the configured cloud
        # remote. This is gated by `RESTIC_PCLOUD_SYNC` and disabled by default
        # to avoid surprises in test environments.
        try:
            if restic_pcloud_sync_enabled():
                print("[stage:restic-push] Pushing restic repo to cloud")
                push_restic_to_cloud()
                print("[stage:restic-push] Restic repo pushed to cloud")
        except Exception as err:
            # Don't fail the overall backup if the push step fails — log and continue.
            print(f"[stage:restic-push] Warning: push to cloud failed: {err}")
        print("[stage:complete] Backup pipeline completed")


if __name__ == "__main__":
    main()
