from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.toolbox.docker.compose import missing_external_volumes
from src.toolbox.docker.health import run_runtime_health_checks


def main() -> None:
    print("[drift] Checking external volume presence")
    missing = missing_external_volumes()
    if missing:
        raise SystemExit(
            "[drift] missing external volumes: " + ", ".join(sorted(missing))
        )

    print("[drift] Running runtime health checks")
    try:
        run_runtime_health_checks()
    except RuntimeError as err:
        raise SystemExit(f"[drift] unhealthy: {err}") from err

    print("[drift] no actionable drift detected")


if __name__ == "__main__":
    main()
