from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from argparse import ArgumentParser
from uuid import uuid4

from src.workflows.pipeline import PIPELINE_STEPS
from src.workflows.workflow_runner import start_checkpoint, run_checkpoint_stages
from src.toolbox.core.runtime import checkpoints_root, locks_root
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.config import runbook_resume_enabled
from src.reconciler.runtime_observer import RuntimeObserver
from src.configuration.state_model import WorkflowState


def _run_check_only() -> None:
    state = WorkflowState(
        workflow="reconcile",
        desired="Healthy",
        runId=str(uuid4()),
        idempotencyToken=str(uuid4()),
    )
    observer = RuntimeObserver()
    try:
        degraded = observer.probe_runtime(state)
        observed = "Degraded" if degraded else "Healthy"
        run_status = "failed" if degraded else "completed"
        print(f"[reconcile] observed={observed} status={run_status}")
        if run_status == "failed":
            sys.exit(1)
    except RuntimeError as err:
        print(f"[reconcile] observed=Degraded status=failed error={err}")
        sys.exit(1)


def _run_full(resume_enabled: bool) -> None:
    checkpoint = start_checkpoint(
        "reconcile",
        "Healthy",
        root=checkpoints_root(),
        resume=resume_enabled,
    )
    print("Running pipeline reconcile...")
    try:
        run_checkpoint_stages(
            checkpoint,
            PIPELINE_STEPS,
            observed_on_failure="Degraded",
        )
        checkpoint.finish(observed="Healthy", ok=True)
        print("[reconcile] observed=Healthy status=completed")
    except SystemExit:
        print("[reconcile] observed=Degraded status=failed")
        raise
    except Exception as err:
        print(f"[reconcile] observed=Degraded status=failed error={err}")
        sys.exit(1)


def main() -> None:
    parser = ArgumentParser(description="Run reconciliation via pipeline")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    resume_enabled = runbook_resume_enabled()

    with RunbookLock("reconcile", locks_root()):
        if args.check_only:
            _run_check_only()
        else:
            _run_full(resume_enabled)


if __name__ == "__main__":
    main()
