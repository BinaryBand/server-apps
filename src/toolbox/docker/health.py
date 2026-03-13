from __future__ import annotations

from src.toolbox.core.polling import ProbeResult, wait_until
from src.toolbox.core.config import rclone_remote

from collections.abc import Callable, Sequence
from typing import TextIO
import shlex
import subprocess


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
    except RuntimeError as err:
        raise RuntimeError(
            _format_command_failure(description, command, last_result, str(err))
        ) from err

    if last_result is None:
        raise RuntimeError(f"{description} failed before the first probe ran.")

    return last_result


def wait_for_container_exec(
    description: str,
    *,
    container: str,
    exec_args: Sequence[str],
    timeout_seconds: float,
    interval_seconds: float,
) -> subprocess.CompletedProcess[str]:
    command = ["docker", "exec", container, *list(exec_args)]
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
    remote = rclone_remote("pcloud")

    exec_checks: list[tuple[str, str, list[str], float, float]] = [
        (
            "Wait for rclone config",
            "rclone",
            ["test", "-f", "/config/rclone/rclone.conf"],
            30,
            1,
        ),
        (
            "Wait for rclone access to MinIO",
            "rclone",
            ["rclone", "lsd", "minio:", "--max-depth", "1"],
            45,
            3,
        ),
        (
            f"Wait for rclone access to {remote}",
            "rclone",
            ["rclone", "lsd", f"{remote}:", "--max-depth", "1"],
            45,
            3,
        ),
        (
            "Wait for Jellyfin log write access",
            "jellyfin",
            ["test", "-w", "/logs"],
            20,
            2,
        ),
    ]

    for (
        description,
        container,
        exec_args,
        timeout_seconds,
        interval_seconds,
    ) in exec_checks:
        wait_for_container_exec(
            description,
            container=container,
            exec_args=exec_args,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
        )

    wait_for_container_health(
        "Wait for Jellyfin health status",
        container="jellyfin",
        timeout_seconds=60,
        interval_seconds=5,
    )


def probe_container_health(container: str) -> bool:
    """Non-blocking single-shot probe. Returns True if running or healthy."""
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
            container,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    status = result.stdout.strip()
    return status in ("healthy", "running")


__all__ = [
    "probe_container_health",
    "run_runtime_health_checks",
    "wait_for_command",
    "wait_for_container_exec",
    "wait_for_container_health",
]
