from __future__ import annotations

from runbook.start import main

from unittest import TestCase, main as unittest_main
from unittest.mock import patch


class StartRunbookTest(TestCase):
    def test_main_runs_health_checks_after_compose_up(self) -> None:
        events: list[str] = []

        def record(event: str):
            def _inner(*args, **kwargs):
                events.append(event)
                if event == "compose_cmd":
                    return ["docker", "compose", "up", "-d"]
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
            patch("runbook.start.compose_cmd", side_effect=record("compose_cmd")),
            patch("runbook.start.subprocess.run", side_effect=record("compose_run")),
            patch(
                "runbook.start.run_runtime_health_checks", side_effect=record("health")
            ),
        ):
            main()

        self.assertEqual(
            events,
            ["volumes", "permissions", "compose_cmd", "compose_run", "health"],
        )


if __name__ == "__main__":
    unittest_main()
