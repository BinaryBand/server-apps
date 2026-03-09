from __future__ import annotations

from runbook.start import main

from unittest import TestCase, main as unittest_main
from unittest.mock import patch


class StartRunbookTest(TestCase):
    def test_main_runs_health_checks_after_permissions_reconcile(self) -> None:
        events: list[str] = []

        def record(event: str):
            def _inner(*args, **kwargs):
                events.append(event)
                return None

            return _inner

        with (
            patch(
                "runbook.start.ensure_external_volumes", side_effect=record("volumes")
            ),
            patch(
                "runbook.start.run_permissions_playbook",
                side_effect=record("permissions"),
            ),
            patch(
                "runbook.start.run_runtime_post_start", side_effect=record("runtime")
            ),
            patch(
                "runbook.start.run_runtime_health_checks", side_effect=record("health")
            ),
        ):
            main()

        self.assertEqual(
            events,
            ["volumes", "permissions", "runtime", "health"],
        )


if __name__ == "__main__":
    unittest_main()
