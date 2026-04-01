from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.managers.checkpoint import OperationCheckpoint
from src.managers.pipeline import PIPELINE_STEPS
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.runtime import checkpoints_root, locks_root

from src.toolbox.core.config import runbook_resume_enabled


def main():
    resume_enabled: bool = runbook_resume_enabled()

    with RunbookLock("start-stop", locks_root()):
        checkpoint = OperationCheckpoint(
            "start", checkpoints_root(), resume=resume_enabled
        )
        checkpoint.start(desired="Healthy")

        print("Initializing apps...")

        for stage_name, step in PIPELINE_STEPS:
            if checkpoint.should_skip_stage(stage_name):
                print(f"[stage:{stage_name}] Skipping already completed stage")
                continue
            print(f"[stage:{stage_name}] Running...")
            try:
                step()
            except RuntimeError as err:
                checkpoint.mark_stage(stage_name, ok=False, message=str(err))
                checkpoint.finish(observed="Degraded", ok=False)
                raise SystemExit(f"[stage:{stage_name}] {err}") from err
            checkpoint.mark_stage(stage_name, ok=True)

        checkpoint.finish(observed="Healthy", ok=True)
        print("Initialization complete.")


if __name__ == "__main__":
    main()
