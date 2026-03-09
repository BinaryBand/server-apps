from __future__ import annotations

from src.utils.docker.health import (
    HealthCheckError,
    run_runtime_health_checks,
    wait_for_command,
)
from src.utils.polling import ProbeResult, wait_until

from io import StringIO
from subprocess import CompletedProcess
from unittest import TestCase, main
from unittest.mock import call, patch


class WaitUntilTest(TestCase):
    def test_wait_until_returns_on_ready_probe(self) -> None:
        attempts = iter(
            [
                ProbeResult(ready=False, detail="starting"),
                ProbeResult(ready=True, detail="healthy"),
            ]
        )

        result = wait_until(
            "Wait for service",
            lambda: next(attempts),
            timeout_seconds=1,
            interval_seconds=0,
            stream=StringIO(),
        )

        self.assertEqual(result, ProbeResult(ready=True, detail="healthy"))

    def test_wait_for_command_reports_command_context(self) -> None:
        failed = CompletedProcess(
            ["docker", "inspect", "jellyfin"],
            returncode=1,
            stdout="",
            stderr="container not found\n",
        )

        with patch("src.utils.docker.health._run_command", return_value=failed):
            with self.assertRaises(HealthCheckError) as err:
                wait_for_command(
                    "Wait for Jellyfin health status",
                    ["docker", "inspect", "jellyfin"],
                    timeout_seconds=0,
                    interval_seconds=0,
                    stream=StringIO(),
                )

        message = str(err.exception)
        self.assertIn("Wait for Jellyfin health status failed.", message)
        self.assertIn("docker inspect jellyfin", message)
        self.assertIn("container not found", message)


class RuntimeHealthChecksTest(TestCase):
    def test_runtime_health_checks_use_expected_sequence(self) -> None:
        with (
            patch("src.utils.docker.health.read_secret", return_value="pcloud"),
            patch("src.utils.docker.health.wait_for_container_exec") as wait_exec,
            patch("src.utils.docker.health.wait_for_container_health") as wait_health,
        ):
            run_runtime_health_checks()

        self.assertEqual(
            wait_exec.call_args_list,
            [
                call(
                    "Wait for rclone config",
                    container="rclone",
                    shell_command="test -f /config/rclone/rclone.conf",
                    timeout_seconds=30,
                    interval_seconds=1,
                ),
                call(
                    "Wait for rclone access to MinIO",
                    container="rclone",
                    shell_command="rclone lsd minio: --max-depth 1",
                    timeout_seconds=45,
                    interval_seconds=3,
                ),
                call(
                    "Wait for rclone access to pcloud",
                    container="rclone",
                    shell_command="rclone lsd pcloud: --max-depth 1",
                    timeout_seconds=45,
                    interval_seconds=3,
                ),
                call(
                    "Wait for Jellyfin log write access",
                    container="jellyfin",
                    shell_command="touch /logs/.jellyfin-log.assert && rm -f /logs/.jellyfin-log.assert",
                    timeout_seconds=20,
                    interval_seconds=2,
                ),
            ],
        )
        wait_health.assert_called_once_with(
            "Wait for Jellyfin health status",
            container="jellyfin",
            timeout_seconds=60,
            interval_seconds=5,
        )


if __name__ == "__main__":
    main()
