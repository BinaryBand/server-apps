from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.toolbox.docker.compose import ensure_external_volumes
from src.toolbox.docker.health import run_runtime_health_checks
from src.toolbox.docker.post_start import run_runtime_post_start
from src.managers.checkpoint import OperationCheckpoint
from src.toolbox.core.locking import RunbookLock
from src.toolbox.core.ansible import run_permissions_playbook
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

        if checkpoint.should_skip_stage("volumes"):
            print("[stage:volumes] Skipping already completed stage")
        else:
            print("[stage:volumes] Ensuring external volumes exist")
            try:
                ensure_external_volumes()
            except RuntimeError as err:
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
            except RuntimeError as err:
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
            except RuntimeError as err:
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
            except RuntimeError as err:
                checkpoint.mark_stage("health", ok=False, message=str(err))
                checkpoint.finish(observed="Degraded", ok=False)
                raise SystemExit(f"[stage:health] {err}") from err
            checkpoint.mark_stage("health", ok=True)

        checkpoint.finish(observed="Healthy", ok=True)
        print("Initialization complete.")


if __name__ == "__main__":
    main()
