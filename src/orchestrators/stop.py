from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.compose import stop_compose_stack
from src.toolbox.docker.wrappers.rclone import cleanup_media_mount
from src.workflows.workflow_runner import (
    StagePolicy,
    run_checkpoint_stage,
    start_checkpoint,
)
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.runtime import checkpoints_root, locks_root


def _run_cleanup_stage(checkpoint) -> None:
    run_checkpoint_stage(
        checkpoint,
        "cleanup",
        cleanup_media_mount,
        StagePolicy(
            observed_on_failure="StopFailed",
            run_message="[stage:cleanup] Cleaning up media mount",
        ),
    )


def _run_shutdown_stage(checkpoint) -> None:
    run_checkpoint_stage(
        checkpoint,
        "shutdown",
        stop_compose_stack,
        StagePolicy(
            observed_on_failure="StopFailed",
            run_message="[stage:shutdown] Stopping containers",
        ),
    )


def _run_stop_stages() -> None:
    checkpoint = start_checkpoint(
        "stop",
        "Stopped",
        root=checkpoints_root(),
        resume=False,
    )

    print("Shutting down server apps...")
    _run_cleanup_stage(checkpoint)
    _run_shutdown_stage(checkpoint)
    checkpoint.finish(observed="Stopped", ok=True)
    print("Shutdown complete.")


def main():
    with RunbookLock("start-stop", locks_root()):
        _run_stop_stages()


if __name__ == "__main__":
    main()
