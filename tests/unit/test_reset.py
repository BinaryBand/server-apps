from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import Mock, patch

from src.orchestrators.reset import main


def test_main_aborts_without_confirmation() -> None:
    """Test that reset aborts when user does not confirm"""
    with (
        patch("src.orchestrators.reset.RunbookLock", return_value=nullcontext()),
        patch("sys.argv", ["reset"]),
        patch("src.orchestrators.reset._confirm_reset", return_value=False),
    ):
        main()  # Should return early without error


def test_main_runs_reset_pipeline_with_yes_flag() -> None:
    """Test that reset runs full pipeline when --yes flag is passed"""
    with (
        patch("src.orchestrators.reset.RunbookLock", return_value=nullcontext()),
        patch("sys.argv", ["reset", "--yes"]),
        patch(
            "src.orchestrators.reset.compose_cmd",
            return_value=["docker", "compose", "down"],
        ),
        patch("subprocess.run", return_value=Mock()),
        patch("src.orchestrators.reset.remove_project_volumes", return_value=(5, 0)),
        patch("src.orchestrators.reset.normalize_reset_permissions", return_value=None),
    ):
        main()


def test_main_runs_dry_run_without_modifications() -> None:
    """Test that dry-run mode prints actions without modifying state"""
    with (
        patch("src.orchestrators.reset.RunbookLock", return_value=nullcontext()),
        patch("sys.argv", ["reset", "--dry-run", "--yes"]),
        patch(
            "src.orchestrators.reset.compose_cmd",
            return_value=["docker", "compose", "down"],
        ),
        patch("subprocess.run", return_value=Mock()) as mock_run,
        patch("src.orchestrators.reset.remove_project_volumes", return_value=(0, 0)),
        patch("src.orchestrators.reset.normalize_reset_permissions", return_value=None),
    ):
        main()


def test_main_handles_permissions_reset_errors() -> None:
    """Test that reset errors during permissions Stage are caught"""
    with (
        patch("src.orchestrators.reset.RunbookLock", return_value=nullcontext()),
        patch("sys.argv", ["reset", "--yes"]),
        patch(
            "src.orchestrators.reset.compose_cmd",
            return_value=["docker", "compose", "down"],
        ),
        patch("subprocess.run", return_value=Mock()),
        patch("src.orchestrators.reset.remove_project_volumes", return_value=(5, 0)),
        patch(
            "src.orchestrators.reset.normalize_reset_permissions",
            side_effect=RuntimeError("Permission reset failed: sudo required"),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected RuntimeError")
        except RuntimeError as err:
            assert "Permission reset failed" in str(err)


def test_main_handles_compose_down_errors() -> None:
    """Test that docker compose down errors are handled"""
    with (
        patch("src.orchestrators.reset.RunbookLock", return_value=nullcontext()),
        patch("sys.argv", ["reset", "--yes"]),
        patch(
            "src.orchestrators.reset.compose_cmd",
            return_value=["docker", "compose", "down"],
        ),
        patch("subprocess.run", side_effect=RuntimeError("docker daemon not running")),
    ):
        try:
            main()
            raise AssertionError("Expected RuntimeError")
        except RuntimeError as err:
            assert "docker daemon not running" in str(err)
