from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.managers.checkpoint import OperationCheckpoint
from src.managers.pipeline import PIPELINE_STEPS
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.runtime import checkpoints_root, locks_root

from src.toolbox.core.config import runbook_resume_enabled


def _start_checkpoint(*, resume_enabled: bool) -> OperationCheckpoint:
    checkpoint = OperationCheckpoint("start", checkpoints_root(), resume=resume_enabled)
    checkpoint.start(desired="Healthy")
    return checkpoint


def _run_stage(checkpoint: OperationCheckpoint, stage_name: str, step: object) -> None:
    if checkpoint.should_skip_stage(stage_name):
        print(f"[stage:{stage_name}] Skipping already completed stage")
        return

    print(f"[stage:{stage_name}] Running...")
    try:
        step()
    except RuntimeError as err:
        checkpoint.mark_stage(stage_name, ok=False, message=str(err))
        checkpoint.finish(observed="Degraded", ok=False)
        raise SystemExit(f"[stage:{stage_name}] {err}") from err

    checkpoint.mark_stage(stage_name, ok=True)


def _run_pipeline(checkpoint: OperationCheckpoint) -> None:
    for stage_name, step in PIPELINE_STEPS:
        _run_stage(checkpoint, stage_name, step)


def main() -> None:
    resume_enabled = runbook_resume_enabled()

    with RunbookLock("start-stop", locks_root()):
        checkpoint = _start_checkpoint(resume_enabled=resume_enabled)

        print("Initializing apps...")

        _run_pipeline(checkpoint)

        checkpoint.finish(observed="Healthy", ok=True)
        print("Initialization complete.")


if __name__ == "__main__":
    main()
