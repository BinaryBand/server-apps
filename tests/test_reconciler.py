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
                patch(
                    "src.managers.reconciler.state_root", return_value=Path(temp_dir)
                ),
                patch(
                    "src.managers.reconciler.required_external_volume_names",
                    return_value=["rclone_config"],
                ),
                patch(
                    "src.managers.reconciler.probe_external_volume",
                    return_value=False,
                ),
                patch("src.managers.reconciler.compose_service_names", return_value=[]),
            ):
                state = reconcile_once(check_only=True)

        self.assertEqual(state.observed, "Degraded")
        self.assertEqual(state.runStatus, "failed")
        condition = next(
            c for c in state.conditions if c.name == "volume:rclone_config"
        )
        self.assertEqual(condition.status, "false")

    def test_check_only_reports_healthy_when_checks_pass(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with (
                patch(
                    "src.managers.reconciler.state_root", return_value=Path(temp_dir)
                ),
                patch(
                    "src.managers.reconciler.required_external_volume_names",
                    return_value=[],
                ),
                patch(
                    "src.managers.reconciler.compose_service_names",
                    return_value=["jellyfin"],
                ),
                patch(
                    "src.managers.reconciler.probe_container_health",
                    return_value=True,
                ) as health_probe,
            ):
                state = reconcile_once(check_only=True)

        health_probe.assert_called_once_with("jellyfin")
        self.assertEqual(state.observed, "Healthy")
        self.assertEqual(state.runStatus, "completed")
        condition = next(c for c in state.conditions if c.name == "service:jellyfin")
        self.assertEqual(condition.status, "true")


if __name__ == "__main__":
    main()
