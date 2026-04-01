from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO
import time


@dataclass(frozen=True)
class ProbeResult:
    ready: bool
    detail: str | None = None


def _normalize_probe(raw_result: ProbeResult | bool) -> ProbeResult:
    return (
        raw_result
        if isinstance(raw_result, ProbeResult)
        else ProbeResult(ready=bool(raw_result))
    )


def _timeout_message(
    description: str, timeout_seconds: float, detail: str | None
) -> str:
    detail_str: str = f" Last status: {detail}." if detail else ""
    return f"Timed out while waiting for {description} after {timeout_seconds:.0f}s{detail_str}"


def _is_timed_out(deadline: float) -> bool:
    return time.monotonic() >= deadline


def _sleep_for_interval(interval_seconds: float) -> None:
    time.sleep(interval_seconds)


def wait_until(
    description: str,
    probe: Callable[[], ProbeResult | bool],
    *,
    timeout_seconds: float,
    interval_seconds: float,
    stream: TextIO | None = None,
) -> ProbeResult:
    deadline: float = time.monotonic() + timeout_seconds

    while True:
        result: ProbeResult = _normalize_probe(probe())

        if result.ready:
            return result

        if _is_timed_out(deadline):
            raise RuntimeError(
                _timeout_message(description, timeout_seconds, result.detail)
            )

        _sleep_for_interval(interval_seconds)


__all__ = ["ProbeResult", "wait_until"]
