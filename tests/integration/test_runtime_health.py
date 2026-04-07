from __future__ import annotations

from src.observability.health import (
    CommandWaitSpec,
    ContainerExecWaitSpec,
    ContainerHealthWaitSpec,
    run_runtime_health_checks,
    wait_for_command,
)
from src.toolbox.core.polling import ProbeResult, WaitConfig, wait_until

from io import StringIO
from subprocess import CompletedProcess
from unittest.mock import call, patch
import pytest


def test_wait_until_returns_on_ready_probe() -> None:
    attempts = iter(
        [
            ProbeResult(ready=False, detail="starting"),
            ProbeResult(ready=True, detail="healthy"),
        ]
    )

    result = wait_until(
        "Wait for service",
        lambda: next(attempts),
        WaitConfig(timeout_seconds=1, interval_seconds=0),
        stream=StringIO(),
    )

    assert result == ProbeResult(ready=True, detail="healthy")


def test_wait_for_command_reports_command_context() -> None:
    failed = CompletedProcess(
        ["docker", "inspect", "jellyfin"],
        returncode=1,
        stdout="",
        stderr="container not found\n",
    )

    with patch("src.observability.health._run_command", return_value=failed):
        with pytest.raises(RuntimeError) as err:
            wait_for_command(
                CommandWaitSpec(
                    description="Wait for Jellyfin health status",
                    command=["docker", "inspect", "jellyfin"],
                    timeout_seconds=0,
                    interval_seconds=0,
                ),
                stream=StringIO(),
            )

    message = str(err.value)
    assert "Wait for Jellyfin health status failed." in message
    assert "docker inspect jellyfin" in message
    assert "container not found" in message


def test_runtime_health_checks_use_expected_sequence() -> None:
    with (
        patch("src.toolbox.core.config.rclone_remote", return_value="pcloud"),
        patch("src.observability.health.wait_for_container_exec") as wait_exec,
        patch("src.observability.health.wait_for_container_health") as wait_health,
    ):
        run_runtime_health_checks()

    assert wait_exec.call_args_list == [
        call(
            ContainerExecWaitSpec(
                description="Wait for rclone config",
                container="rclone",
                exec_args=["test", "-f", "/config/rclone/rclone.conf"],
                timeout_seconds=30,
                interval_seconds=1,
            ),
        ),
        call(
            ContainerExecWaitSpec(
                description="Wait for rclone access to MinIO",
                container="rclone",
                exec_args=["rclone", "lsd", "minio:", "--max-depth", "1"],
                timeout_seconds=45,
                interval_seconds=3,
            ),
        ),
        call(
            ContainerExecWaitSpec(
                description="Wait for rclone access to pcloud",
                container="rclone",
                exec_args=["rclone", "lsd", "pcloud:", "--max-depth", "1"],
                timeout_seconds=45,
                interval_seconds=3,
            ),
        ),
        call(
            ContainerExecWaitSpec(
                description="Wait for Jellyfin log write access",
                container="jellyfin",
                exec_args=["test", "-w", "/logs"],
                timeout_seconds=20,
                interval_seconds=2,
            ),
        ),
        call(
            ContainerExecWaitSpec(
                description="Wait for Jellyfin media read-only access",
                container="jellyfin",
                exec_args=[
                    "sh",
                    "-lc",
                    'grep -q " /media " /proc/self/mountinfo && test -r /media && ! test -w /media && ls /media >/dev/null',
                ],
                timeout_seconds=30,
                interval_seconds=3,
            ),
        ),
    ]
    wait_health.assert_called_once_with(
        ContainerHealthWaitSpec(
            description="Wait for Jellyfin health status",
            container="jellyfin",
            timeout_seconds=60,
            interval_seconds=5,
        )
    )
