from __future__ import annotations

from src.toolbox.core.polling import ProbeResult, wait_until
from src.toolbox.core.config import rclone_remote

from collections.abc import Callable, Sequence
from typing import Any, TextIO
import shlex
import subprocess


_EXEC_CHECKS_BASE: tuple[tuple[str, str, list[str], float, float], ...] = (
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
        "Wait for Jellyfin log write access",
        "jellyfin",
        ["test", "-w", "/logs"],
        20,
        2,
    ),
)


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


def _create_command_probe(
    command: Sequence[str],
    predicate: Callable[[subprocess.CompletedProcess[str]], bool],
    formatter: Callable[[subprocess.CompletedProcess[str]], str],
) -> tuple[Callable[[], ProbeResult], dict[str, Any]]:
    """Create a probe function and mutable state for running commands."""
    state: dict[str, Any] = {"last_result": None}

    def _probe() -> ProbeResult:
        state["last_result"] = _run_command(command)
        return ProbeResult(
            ready=predicate(state["last_result"]),
            detail=formatter(state["last_result"]),
        )

    return _probe, state


def _run_wait_loop(
    description: str,
    probe: Callable[[], ProbeResult],
    *,
    timeout_seconds: float,
    interval_seconds: float,
    stream: TextIO | None,
) -> None:
    wait_until(
        description,
        probe,
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
        stream=stream,
    )


def _raise_command_failure(
    description: str,
    command: Sequence[str],
    state: dict[str, Any],
    err: RuntimeError,
) -> None:
    raise RuntimeError(
        _format_command_failure(description, command, state["last_result"], str(err))
    ) from err


def _require_last_result(
    description: str, state: dict[str, Any]
) -> subprocess.CompletedProcess[str]:
    if state["last_result"] is None:
        raise RuntimeError(f"{description} failed before the first probe ran.")
    return state["last_result"]


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
    _probe, state = _create_command_probe(command, predicate, formatter)

    try:
        _run_wait_loop(
            description,
            _probe,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
            stream=stream,
        )
    except RuntimeError as err:
        _raise_command_failure(description, command, state, err)

    return _require_last_result(description, state)


def _healthy_status(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and result.stdout.strip() == "healthy"


def _health_detail(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout.strip() or _default_command_detail(result)


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
        success_predicate=_healthy_status,
        detail_formatter=_health_detail,
    )


def _exec_check_table() -> list[tuple[str, str, list[str], float, float]]:
    """Return the table of container exec health checks."""
    remote = rclone_remote("pcloud")
    checks = list(_EXEC_CHECKS_BASE)
    checks.insert(
        2,
        (
            f"Wait for rclone access to {remote}",
            "rclone",
            ["rclone", "lsd", f"{remote}:", "--max-depth", "1"],
            45,
            3,
        ),
    )
    return checks


def run_runtime_health_checks() -> None:
    checks = _exec_check_table()

    for (
        description,
        container,
        exec_args,
        timeout_seconds,
        interval_seconds,
    ) in checks:
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


def probe_minio_media_public() -> bool:
    """Return True if the myminio/media bucket has anonymous download access."""
    result = subprocess.run(
        ["docker", "exec", "minio", "mc", "stat", "myminio/media"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "anonymous: enabled" in result.stdout.lower()


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
    "probe_minio_media_public",
    "run_runtime_health_checks",
    "wait_for_command",
    "wait_for_container_exec",
    "wait_for_container_health",
]
