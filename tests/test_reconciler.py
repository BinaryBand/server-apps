from __future__ import annotations

from src.managers.reconciler import reconcile_once

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch


class ReconcilerTest(TestCase):
    def test_check_only_reports_degraded_when_volume_drift_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with (
                patch("src.managers.reconciler.state_root", return_value=Path(temp_dir)),
                patch(
                    "src.managers.reconciler.missing_external_volumes",
                    return_value=["rclone_config"],
                ),
            ):
                state = reconcile_once(check_only=True)

        self.assertEqual(state.observed, "Degraded")
        self.assertEqual(state.runStatus, "failed")

    def test_check_only_reports_healthy_when_checks_pass(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with (
                patch("src.managers.reconciler.state_root", return_value=Path(temp_dir)),
                patch("src.managers.reconciler.missing_external_volumes", return_value=[]),
                patch("src.managers.reconciler.run_runtime_health_checks") as health,
            ):
                state = reconcile_once(check_only=True)

        health.assert_called_once_with()
        self.assertEqual(state.observed, "Healthy")
        self.assertEqual(state.runStatus, "completed")


if __name__ == "__main__":
    main()
