from __future__ import annotations

from src.toolbox.core.polling import ProbeResult, WaitConfig, wait_until
from src.toolbox.core.config import rclone_remote

from collections.abc import Callable, Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CommandWaitSpec:
    description: str
    command: Sequence[str]
    timeout_seconds: float
    interval_seconds: float


@dataclass(frozen=True)
class ContainerExecWaitSpec:
    description: str
    container: str
    exec_args: Sequence[str]
    timeout_seconds: float
    interval_seconds: float


@dataclass(frozen=True)
class ContainerHealthWaitSpec:
    description: str
    container: str
    timeout_seconds: float
    interval_seconds: float


CommandPredicate = Callable[[subprocess.CompletedProcess[str]], bool]
CommandFormatter = Callable[[subprocess.CompletedProcess[str]], str]


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
    predicate: CommandPredicate,
    formatter: CommandFormatter,
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


def _run_wait_loop(spec: CommandWaitSpec, probe: Callable[[], ProbeResult], stream: TextIO | None) -> None:
    wait_until(
        spec.description,
        probe,
        WaitConfig(
            timeout_seconds=spec.timeout_seconds,
            interval_seconds=spec.interval_seconds,
        ),
        stream=stream,
    )


def _raise_command_failure(
    spec: CommandWaitSpec,
    state: dict[str, Any],
    err: RuntimeError,
) -> None:
    raise RuntimeError(
        _format_command_failure(
            spec.description,
            spec.command,
            state["last_result"],
            str(err),
        )
    ) from err


def _require_last_result(spec: CommandWaitSpec, state: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    if state["last_result"] is None:
        raise RuntimeError(f"{spec.description} failed before the first probe ran.")
    return state["last_result"]


def wait_for_command(
    spec: CommandWaitSpec,
    *,
    success_predicate: CommandPredicate | None = None,
    detail_formatter: CommandFormatter | None = None,
    stream: TextIO | None = None,
) -> subprocess.CompletedProcess[str]:
    predicate = success_predicate or (lambda result: result.returncode == 0)
    formatter = detail_formatter or _default_command_detail
    _probe, state = _create_command_probe(spec.command, predicate, formatter)

    try:
        _run_wait_loop(spec, _probe, stream)
    except RuntimeError as err:
        _raise_command_failure(spec, state, err)

    return _require_last_result(spec, state)


def _healthy_status(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode == 0 and result.stdout.strip() == "healthy"


def _health_detail(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout.strip() or _default_command_detail(result)


def wait_for_container_exec(spec: ContainerExecWaitSpec) -> subprocess.CompletedProcess[str]:
    command = ["docker", "exec", spec.container, *list(spec.exec_args)]
    return wait_for_command(
        CommandWaitSpec(
            description=spec.description,
            command=command,
            timeout_seconds=spec.timeout_seconds,
            interval_seconds=spec.interval_seconds,
        ),
    )


def wait_for_container_health(spec: ContainerHealthWaitSpec) -> subprocess.CompletedProcess[str]:
    command = [
        "docker",
        "inspect",
        "-f",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        spec.container,
    ]
    return wait_for_command(
        CommandWaitSpec(
            description=spec.description,
            command=command,
            timeout_seconds=spec.timeout_seconds,
            interval_seconds=spec.interval_seconds,
        ),
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


def _run_exec_checks(checks: list[tuple[str, str, list[str], float, float]]) -> None:
    for (
        description,
        container,
        exec_args,
        timeout_seconds,
        interval_seconds,
    ) in checks:
        wait_for_container_exec(
            ContainerExecWaitSpec(
                description=description,
                container=container,
                exec_args=exec_args,
                timeout_seconds=timeout_seconds,
                interval_seconds=interval_seconds,
            )
        )


def _run_jellyfin_health_check() -> None:
    wait_for_container_health(
        ContainerHealthWaitSpec(
            description="Wait for Jellyfin health status",
            container="jellyfin",
            timeout_seconds=60,
            interval_seconds=5,
        )
    )


def run_runtime_health_checks() -> None:
    _run_exec_checks(_exec_check_table())
    _run_jellyfin_health_check()


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
