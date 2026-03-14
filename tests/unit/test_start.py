from __future__ import annotations

from unittest.mock import patch

from src.orchestrators.start import main


def test_main_runs_health_checks_after_permissions_reconcile() -> None:
    events: list[str] = []

    def record(event: str):
        def _inner(*args, **kwargs):
            events.append(event)
            return None

        return _inner

    with (
        patch(
            "src.orchestrators.start.ensure_external_volumes",
            side_effect=record("volumes"),
        ),
        patch(
            "src.orchestrators.start.run_permissions_playbook",
            side_effect=record("permissions"),
        ),
        patch(
            "src.orchestrators.start.run_runtime_post_start",
            side_effect=record("runtime"),
        ),
        patch(
            "src.orchestrators.start.run_runtime_health_checks",
            side_effect=record("health"),
        ),
    ):
        main()

    assert events == ["volumes", "permissions", "runtime", "health"]
