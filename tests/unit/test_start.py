from __future__ import annotations

from contextlib import nullcontext
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
        patch("src.workflows.pipeline.ensure_secrets", side_effect=record("setup")),
        patch(
            "src.workflows.pipeline.ensure_external_volumes",
            side_effect=record("volumes"),
        ),
        patch(
            "src.workflows.pipeline.run_permissions_playbook",
            side_effect=record("permissions"),
        ),
        patch(
            "src.workflows.pipeline.run_runtime_post_start",
            side_effect=record("runtime"),
        ),
        patch(
            "src.workflows.pipeline.run_runtime_health_checks",
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

    assert events == ["setup", "volumes", "permissions", "runtime", "health"]


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


def test_main_handles_permission_errors_during_workflow() -> None:
    """Test that permission errors during workflow stages are caught and reported"""
    with (
        patch(
            "src.orchestrators.start.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.start.ensure_docker_daemon_access",
            return_value=None,
        ),
        patch("src.workflows.pipeline.ensure_secrets", return_value=None),
        patch(
            "src.workflows.pipeline.ensure_external_volumes",
            return_value=None,
        ),
        patch(
            "src.workflows.pipeline.run_permissions_playbook",
            side_effect=RuntimeError(
                "Failed to run permissions playbook: Operation not permitted: "
                "/media/owen/Passport/minio"
            ),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "Permission" in str(err) or "Operation not permitted" in str(err)
