from src.utils.docker.compose import compose_cmd, ensure_external_volumes
from src.utils.docker.health import HealthCheckError, run_runtime_health_checks
from src.utils.permissions import run_permissions_playbook

import subprocess


def main():
    print("Initializing apps...")

    print("[stage:volumes] Ensuring external volumes exist")
    ensure_external_volumes()

    print("[stage:permissions] Reconciling runtime permissions")
    run_permissions_playbook(mode="runtime")

    print("[stage:compose] Starting compose services")
    subprocess.run(compose_cmd("up", "-d"), check=True)

    print("[stage:health] Waiting for runtime health checks")
    try:
        run_runtime_health_checks()
    except HealthCheckError as err:
        raise SystemExit(f"[stage:health] {err}") from err
    
    print("Initialization complete.")


if __name__ == "__main__":
    main()
