from __future__ import annotations

from unittest.mock import patch
from contextlib import nullcontext

from src.orchestrators.stop import main


def test_main_runs_cleanup_and_shutdown_stages() -> None:
    """Test that stop command runs cleanup and shutdown stages in order"""
    events: list[str] = []

    def record(event: str):
        def _inner(*args, **kwargs):
            events.append(event)
            return None

        return _inner

    with (
        patch(
            "src.orchestrators.stop.cleanup_media_mount",
            side_effect=record("cleanup"),
        ),
        patch(
            "src.orchestrators.stop.stop_compose_stack",
            side_effect=record("shutdown"),
        ),
        patch(
            "src.orchestrators.stop.RunbookLock",
            return_value=nullcontext(),
        ),
    ):
        main()

    assert events == ["cleanup", "shutdown"]


def test_main_handles_cleanup_errors() -> None:
    """Test that cleanup stage errors are caught and reported"""
    with (
        patch(
            "src.orchestrators.stop.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.stop.cleanup_media_mount",
            side_effect=RuntimeError("Cleanup failed: mount busy"),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "Cleanup failed" in str(err) or "StopFailed" in str(err)


def test_main_handles_shutdown_errors() -> None:
    """Test that shutdown stage errors are caught and reported"""
    with (
        patch(
            "src.orchestrators.stop.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.stop.cleanup_media_mount",
            return_value=None,
        ),
        patch(
            "src.orchestrators.stop.stop_compose_stack",
            side_effect=RuntimeError("Docker daemon unavailable"),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "Docker daemon unavailable" in str(err) or "StopFailed" in str(err)
