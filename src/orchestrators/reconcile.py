from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from argparse import ArgumentParser

from src.infra.config import runbook_resume_enabled
from src.infra.locking import RunbookLock
from src.infra.runtime import checkpoints_root, locks_root
from src.observability.health import run_runtime_health_checks
from src.workflows.pipeline import PIPELINE_STEPS
from src.workflows.workflow_runner import run_checkpoint_stages, start_checkpoint


def _run_check_only() -> None:
    try:
        run_runtime_health_checks()
        print("[reconcile] observed=Healthy status=completed")
    except (RuntimeError, SystemExit) as err:
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
