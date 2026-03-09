from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.docker.compose import ensure_external_volumes
from src.utils.docker.health import HealthCheckError, run_runtime_health_checks
from src.utils.docker.lifecycle.runtime_post_start import run_runtime_post_start
from src.utils.docker.post_start.errors import RuntimePostStartError
from src.utils.permissions import run_permissions_playbook


def main():
    print("Initializing apps...")

    print("[stage:volumes] Ensuring external volumes exist")
    ensure_external_volumes()

    print("[stage:permissions] Reconciling runtime permissions")
    run_permissions_playbook(mode="runtime")

    print("[stage:runtime] Applying post-start runtime actions")
    try:
        run_runtime_post_start()
    except RuntimePostStartError as err:
        raise SystemExit(f"[stage:runtime] {err}") from err

    print("[stage:health] Waiting for runtime health checks")
    try:
        run_runtime_health_checks()
    except HealthCheckError as err:
        raise SystemExit(f"[stage:health] {err}") from err

    print("Initialization complete.")


if __name__ == "__main__":
    main()
