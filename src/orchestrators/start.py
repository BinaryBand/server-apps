from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.workflows.pipeline import PIPELINE_STEPS
from src.workflows.workflow_runner import run_checkpoint_stages, start_checkpoint
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.runtime import checkpoints_root, locks_root
from src.toolbox.docker.health import ensure_docker_daemon_access

from src.toolbox.core.config import runbook_resume_enabled


def _run_preflight() -> None:
    try:
        ensure_docker_daemon_access()
    except RuntimeError as err:
        raise SystemExit(f"[preflight] {err}") from err


def _run_start_workflow(resume_enabled: bool) -> None:
    checkpoint = start_checkpoint(
        "start",
        "Healthy",
        root=checkpoints_root(),
        resume=resume_enabled,
    )

    print("Initializing apps...")
    run_checkpoint_stages(
        checkpoint,
        PIPELINE_STEPS,
        observed_on_failure="Degraded",
    )
    checkpoint.finish(observed="Healthy", ok=True)
    print("Initialization complete.")


def main() -> None:
    resume_enabled = runbook_resume_enabled()

    with RunbookLock("start-stop", locks_root()):
        _run_preflight()
        _run_start_workflow(resume_enabled)


if __name__ == "__main__":
    main()
