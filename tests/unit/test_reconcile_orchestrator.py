from __future__ import annotations

from unittest.mock import Mock, patch

from src.orchestrators.reconcile import main


def test_main_runs_reconcile_once_and_reports_state() -> None:
    """Test that reconcile command runs reconcile_once and reports the result"""
    mock_state = Mock()
    mock_state.observed = "Healthy"
    mock_state.runStatus = "ok"

    with (
        patch("src.orchestrators.reconcile.reconcile_once", return_value=mock_state),
        patch("sys.argv", ["reconcile"]),
    ):
        main()  # Should exit normally


def test_main_passes_check_only_flag() -> None:
    """Test that reconcile respects the --check-only flag"""
    mock_state = Mock()
    mock_state.observed = "Healthy"
    mock_state.runStatus = "ok"

    with (
        patch("src.orchestrators.reconcile.reconcile_once", return_value=mock_state) as mock_reconcile,
        patch("sys.argv", ["reconcile", "--check-only"]),
    ):
        main()
        mock_reconcile.assert_called_once_with(check_only=True)


def test_main_exits_with_failure_when_reconcile_fails() -> None:
    """Test that reconcile exits with code 1 when reconcile_once fails"""
    mock_state = Mock()
    mock_state.observed = "Degraded"
    mock_state.runStatus = "failed"

    with (
        patch("src.orchestrators.reconcile.reconcile_once", return_value=mock_state),
        patch("sys.argv", ["reconcile"]),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert err.code == 1


def test_main_handles_reconcile_exceptions() -> None:
    """Test that reconcile exceptions are caught and cause exit"""
    with (
        patch(
            "src.orchestrators.reconcile.reconcile_once",
            side_effect=RuntimeError("Reconcile error: docker daemon unavailable"),
        ),
        patch("sys.argv", ["reconcile"]),
    ):
        try:
            main()
            raise AssertionError("Expected RuntimeError")
        except RuntimeError as err:
            assert "Reconcile error" in str(err)
