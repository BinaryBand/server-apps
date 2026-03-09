from __future__ import annotations

from src.utils.polling import PollingTimeoutError, ProbeResult, wait_until
from src.utils.secrets import read_secret

from collections.abc import Callable, Sequence
from typing import TextIO
import shlex
import subprocess


class HealthCheckError(RuntimeError):
    """Raised when runtime health checks fail."""


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


def _default_command_detail(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode == 0:
        stdout = result.stdout.strip()
        return stdout or "ready"

    stderr = result.stderr.strip()
    if stderr:
        return stderr.splitlines()[0]

    stdout = result.stdout.strip()
    if stdout:
        return stdout.splitlines()[0]

    return f"exit {result.returncode}"


def _format_command_failure(
    description: str,
    command: Sequence[str],
    last_result: subprocess.CompletedProcess[str] | None,
    reason: str,
) -> str:
    lines = [
        f"{description} failed.",
        f"Command: {shlex.join(list(command))}",
        reason,
    ]

    if last_result is not None:
        lines.append(f"Return code: {last_result.returncode}")
        stdout = last_result.stdout.strip()
        stderr = last_result.stderr.strip()
        if stdout:
            lines.append(f"stdout:\n{stdout}")
        if stderr:
            lines.append(f"stderr:\n{stderr}")

    return "\n".join(lines)


def wait_for_command(
    description: str,
    command: Sequence[str],
    *,
    timeout_seconds: float,
    interval_seconds: float,
    success_predicate: Callable[[subprocess.CompletedProcess[str]], bool] | None = None,
    detail_formatter: Callable[[subprocess.CompletedProcess[str]], str] | None = None,
    stream: TextIO | None = None,
) -> subprocess.CompletedProcess[str]:
    predicate = success_predicate or (lambda result: result.returncode == 0)
    formatter = detail_formatter or _default_command_detail
    last_result: subprocess.CompletedProcess[str] | None = None

    def _probe() -> ProbeResult:
        nonlocal last_result
        last_result = _run_command(command)
        return ProbeResult(
            ready=predicate(last_result),
            detail=formatter(last_result),
        )

    try:
        wait_until(
            description,
            _probe,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
            stream=stream,
        )
    except PollingTimeoutError as err:
        raise HealthCheckError(
            _format_command_failure(description, command, last_result, str(err))
        ) from err

    if last_result is None:
        raise HealthCheckError(f"{description} failed before the first probe ran.")

    return last_result


def wait_for_container_exec(
    description: str,
    *,
    container: str,
    shell_command: str,
    timeout_seconds: float,
    interval_seconds: float,
) -> subprocess.CompletedProcess[str]:
    command = ["docker", "exec", container, "sh", "-lc", shell_command]
    return wait_for_command(
        description,
        command,
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
    )


def wait_for_container_health(
    description: str,
    *,
    container: str,
    timeout_seconds: float,
    interval_seconds: float,
) -> subprocess.CompletedProcess[str]:
    command = [
        "docker",
        "inspect",
        "-f",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        container,
    ]
    return wait_for_command(
        description,
        command,
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
        success_predicate=lambda result: (
            result.returncode == 0 and result.stdout.strip() == "healthy"
        ),
        detail_formatter=lambda result: (
            result.stdout.strip() or _default_command_detail(result)
        ),
    )


def run_runtime_health_checks() -> None:
    remote = read_secret("RCLONE_REMOTE", "pcloud") or "pcloud"

    exec_checks: list[tuple[str, str, str, float, float]] = [
        (
            "Wait for rclone config",
            "rclone",
            "test -f /config/rclone/rclone.conf",
            30,
            1,
        ),
        (
            "Wait for rclone access to MinIO",
            "rclone",
            "rclone lsd minio: --max-depth 1",
            45,
            3,
        ),
        (
            f"Wait for rclone access to {remote}",
            "rclone",
            f"rclone lsd {shlex.quote(remote)}: --max-depth 1",
            45,
            3,
        ),
        (
            "Wait for Jellyfin log write access",
            "jellyfin",
            "touch /logs/.jellyfin-log.assert && rm -f /logs/.jellyfin-log.assert",
            20,
            2,
        ),
    ]

    for (
        description,
        container,
        shell_command,
        timeout_seconds,
        interval_seconds,
    ) in exec_checks:
        wait_for_container_exec(
            description,
            container=container,
            shell_command=shell_command,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
        )

    wait_for_container_health(
        "Wait for Jellyfin health status",
        container="jellyfin",
        timeout_seconds=60,
        interval_seconds=5,
    )
