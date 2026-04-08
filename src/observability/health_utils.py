from __future__ import annotations

import shlex
import subprocess
from collections.abc import Sequence
from typing import Any, Callable

from src.toolbox.core.polling import ProbeResult, WaitConfig, wait_until


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
    state: dict[str, Any] = {"last_result": None}

    def _probe() -> ProbeResult:
        state["last_result"] = _run_command(command)
        return ProbeResult(
            ready=predicate(state["last_result"]),
            detail=formatter(state["last_result"]),
        )

    return _probe, state


def _run_wait_loop(spec: Any, probe: Callable[[], ProbeResult], stream: Any | None) -> None:
    wait_until(
        spec.description,
        probe,
        WaitConfig(
            timeout_seconds=spec.timeout_seconds,
            interval_seconds=spec.interval_seconds,
        ),
        stream=stream,
    )


def _raise_command_failure(spec: Any, state: dict[str, Any], err: RuntimeError) -> None:
    raise RuntimeError(
        _format_command_failure(
            spec.description,
            spec.command,
            state["last_result"],
            str(err),
        )
    ) from err


def _require_last_result(spec: Any, state: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    if state["last_result"] is None:
        raise RuntimeError(f"{spec.description} failed before the first probe ran.")
    return state["last_result"]
