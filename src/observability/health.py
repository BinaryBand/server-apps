from __future__ import annotations

from src.toolbox.core.polling import ProbeResult, WaitConfig, wait_until
from src.toolbox.core.config import rclone_remote

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TextIO
import subprocess

from src.observability.health_utils import (
    _run_command,
    _default_command_detail,
    _format_command_failure,
)


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
    (
        "Wait for Jellyfin media read-only access",
        "jellyfin",
        [
            "sh",
            "-lc",
            'grep -q " /media " /proc/self/mountinfo && test -r /media && ! test -w /media && ls /media >/dev/null',
        ],
        30,
        3,
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


def _docker_socket_permission_denied(stderr: str) -> bool:
    lowered = stderr.lower()
    return "permission denied" in lowered and "docker.sock" in lowered


def _docker_daemon_access_error(detail: str) -> str:
    if _docker_socket_permission_denied(detail):
        return (
            "Docker daemon access denied for current user. "
            "Grant access to /var/run/docker.sock (for example via docker group membership) "
            "and start a fresh shell/session before retrying. "
            f"Details: {detail}"
        )
    return (
        "Docker daemon is not reachable from this shell. "
        "Ensure the Docker service is running and the current context/socket is valid. "
        f"Details: {detail}"
    )


def ensure_docker_daemon_access() -> None:
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return

    detail = (result.stderr or "").strip() or "docker info failed"
    raise RuntimeError(_docker_daemon_access_error(detail))


def _resolve_wait_behavior(
    success_predicate: CommandPredicate | None,
    detail_formatter: CommandFormatter | None,
) -> tuple[CommandPredicate, CommandFormatter]:
    predicate = success_predicate or (lambda result: result.returncode == 0)
    formatter = detail_formatter or _default_command_detail
    return predicate, formatter


def _run_wait_loop(
    spec: CommandWaitSpec,
    *,
    predicate: CommandPredicate,
    formatter: CommandFormatter,
    stream: TextIO | None,
) -> subprocess.CompletedProcess[str] | None:
    state: dict[str, Any] = {"last_result": None}

    def _probe() -> ProbeResult:
        state["last_result"] = _run_command(spec.command)
        result: subprocess.CompletedProcess[str] = state["last_result"]
        return ProbeResult(ready=predicate(result), detail=formatter(result))

    wait_until(
        spec.description,
        _probe,
        WaitConfig(
            timeout_seconds=spec.timeout_seconds,
            interval_seconds=spec.interval_seconds,
        ),
        stream=stream,
    )
    return state.get("last_result")


def _require_last_result(
    description: str,
    last_result: subprocess.CompletedProcess[str] | None,
) -> subprocess.CompletedProcess[str]:
    if last_result is None:
        raise RuntimeError(f"{description} failed before the first probe ran.")
    return last_result


def _raise_wait_failure(
    spec: CommandWaitSpec,
    last_result: subprocess.CompletedProcess[str] | None,
    err: RuntimeError,
) -> None:
    raise RuntimeError(
        _format_command_failure(
            spec.description,
            spec.command,
            last_result,
            str(err),
        )
    ) from err


def wait_for_command(
    spec: CommandWaitSpec,
    *,
    success_predicate: CommandPredicate | None = None,
    detail_formatter: CommandFormatter | None = None,
    stream: TextIO | None = None,
) -> subprocess.CompletedProcess[str]:
    predicate, formatter = _resolve_wait_behavior(success_predicate, detail_formatter)
    last_result: subprocess.CompletedProcess[str] | None = None

    try:
        last_result = _run_wait_loop(
            spec,
            predicate=predicate,
            formatter=formatter,
            stream=stream,
        )
    except RuntimeError as err:
        _raise_wait_failure(spec, last_result, err)

    return _require_last_result(spec.description, last_result)


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
    result = subprocess.run(
        ["docker", "exec", "minio", "mc", "stat", "myminio/media"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "anonymous: enabled" in result.stdout.lower()


def probe_container_health(container: str) -> bool:
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
    "CommandWaitSpec",
    "ContainerExecWaitSpec",
    "ContainerHealthWaitSpec",
    "ensure_docker_daemon_access",
    "probe_container_health",
    "probe_minio_media_public",
    "run_runtime_health_checks",
    "wait_for_command",
    "wait_for_container_exec",
    "wait_for_container_health",
]
