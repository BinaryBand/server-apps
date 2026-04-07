from __future__ import annotations

from unittest.mock import patch
from contextlib import nullcontext

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
            "src.managers.pipeline.ensure_external_volumes",
            side_effect=record("volumes"),
        ),
        patch(
            "src.managers.pipeline.run_permissions_playbook",
            side_effect=record("permissions"),
        ),
        patch(
            "src.managers.pipeline.run_runtime_post_start",
            side_effect=record("runtime"),
        ),
        patch(
            "src.managers.pipeline.sync_media",
            side_effect=record("media-sync"),
        ),
        patch(
            "src.managers.pipeline.run_runtime_health_checks",
            side_effect=record("health"),
        ),
        patch(
            "src.orchestrators.start.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.start.ensure_docker_daemon_access",
            return_value=None,
        ),
    ):
        main()

    assert events == ["volumes", "permissions", "runtime", "media-sync", "health"]


def test_main_fails_fast_when_docker_preflight_fails() -> None:
    with (
        patch(
            "src.orchestrators.start.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.start.ensure_docker_daemon_access",
            side_effect=RuntimeError("docker unavailable"),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "[preflight] docker unavailable" in str(err)
