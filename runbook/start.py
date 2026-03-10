from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.docker.compose import ensure_external_volumes
from src.utils.docker.health import HealthCheckError, run_runtime_health_checks
from src.utils.docker.lifecycle.runtime_post_start import run_runtime_post_start
from src.utils.docker.post_start.errors import RuntimePostStartError
from src.utils.checkpoint import OperationCheckpoint
from src.utils.locking import RunbookLock
from src.utils.permissions import run_permissions_playbook
from src.utils.runtime import checkpoints_root, locks_root

import os


def main():
    resume_enabled = os.getenv("RUNBOOK_RESUME", "0") in {"1", "true", "True", "yes"}

    with RunbookLock("start-stop", locks_root()):
        checkpoint = OperationCheckpoint(
            "start", checkpoints_root(), resume=resume_enabled
        )
        checkpoint.start(desired="Healthy")

        print("Initializing apps...")

        if checkpoint.should_skip_stage("volumes"):
            print("[stage:volumes] Skipping already completed stage")
        else:
            print("[stage:volumes] Ensuring external volumes exist")
            try:
                ensure_external_volumes()
            except Exception as err:
                checkpoint.mark_stage("volumes", ok=False, message=str(err))
                checkpoint.finish(observed="Degraded", ok=False)
                raise SystemExit(f"[stage:volumes] {err}") from err
            checkpoint.mark_stage("volumes", ok=True)

        if checkpoint.should_skip_stage("permissions"):
            print("[stage:permissions] Skipping already completed stage")
        else:
            print("[stage:permissions] Reconciling runtime permissions")
            try:
                run_permissions_playbook(mode="runtime")
            except Exception as err:
                checkpoint.mark_stage("permissions", ok=False, message=str(err))
                checkpoint.finish(observed="Degraded", ok=False)
                raise SystemExit(f"[stage:permissions] {err}") from err
            checkpoint.mark_stage("permissions", ok=True)

        if checkpoint.should_skip_stage("runtime"):
            print("[stage:runtime] Skipping already completed stage")
        else:
            print("[stage:runtime] Applying post-start runtime actions")
            try:
                run_runtime_post_start()
            except RuntimePostStartError as err:
                checkpoint.mark_stage("runtime", ok=False, message=str(err))
                checkpoint.finish(observed="Degraded", ok=False)
                raise SystemExit(f"[stage:runtime] {err}") from err
            checkpoint.mark_stage("runtime", ok=True)

        if checkpoint.should_skip_stage("health"):
            print("[stage:health] Skipping already completed stage")
        else:
            print("[stage:health] Waiting for runtime health checks")
            try:
                run_runtime_health_checks()
            except HealthCheckError as err:
                checkpoint.mark_stage("health", ok=False, message=str(err))
                checkpoint.finish(observed="Degraded", ok=False)
                raise SystemExit(f"[stage:health] {err}") from err
            checkpoint.mark_stage("health", ok=True)

        checkpoint.finish(observed="Healthy", ok=True)
        print("Initialization complete.")


if __name__ == "__main__":
    main()
