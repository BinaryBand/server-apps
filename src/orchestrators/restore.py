import sys
from argparse import ArgumentParser, Namespace

from src.adapters.rclone.stream_sync import RcloneStreamSync
from src.backup.restore import recent_snapshots, restore_snapshot
from src.backup.stage_runner import run_restore_stage
from src.configuration.backup_config import BackupConfig, StreamSource
from src.infra.config import runbook_resume_enabled
from src.infra.locking import RunbookLock
from src.infra.runtime import checkpoints_root, locks_root, repo_root
from src.workflows.checkpoint import OperationCheckpoint
from src.workflows.workflow_runner import StagePolicy, run_checkpoint_stage, start_checkpoint

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


def _run_stream_restore(source: StreamSource, checkpoint: OperationCheckpoint) -> None:
    run_checkpoint_stage(
        checkpoint,
        f"restore-stream-{source.name}",
        lambda: run_restore_stage(
            RcloneStreamSync(
                source=source.source,
                destination=source.destination,
                exclude=source.exclude,
            ),
            source.name,
        ),
        StagePolicy(
            observed_on_failure="RestoreFailed",
            run_message=(
                f"[stage:restore-stream-{source.name}] Restoring {source.destination} "
                f"to {source.source}"
            ),
        ),
    )


def _run_restore(args: Namespace, *, resume_enabled: bool) -> None:
    root = repo_root()
    config = BackupConfig.from_toml(root / "configs" / "backup.toml")

    checkpoint = start_checkpoint(
        "restore", "RestoreCompleted", root=checkpoints_root(), resume=resume_enabled
    )

    run_checkpoint_stage(
        checkpoint,
        "restore",
        lambda: restore_snapshot(args.snapshot, DEFAULT_RESTORE_TARGET, args.no_apply_volumes),
        StagePolicy(
            observed_on_failure="RestoreFailed",
            run_message="[stage:restore] Starting snapshot restore",
        ),
    )

    _run_stream_restores(config, checkpoint)

    # compress support removed; no restore-compress stages
    checkpoint.finish(observed="RestoreCompleted", ok=True)
    print("[stage:complete] Restore pipeline completed")


def _run_stream_restores(config: BackupConfig, checkpoint: OperationCheckpoint) -> None:
    for source in config.stream:
        _run_stream_restore(source, checkpoint)


def main() -> None:
    args = _parse_args()
    resume_enabled = runbook_resume_enabled()

    if args.list_snapshots:
        _print_snapshots()
        return

    with RunbookLock("backup-restore-reset", locks_root()):
        _run_restore(args, resume_enabled=resume_enabled)


if __name__ == "__main__":
    main()
