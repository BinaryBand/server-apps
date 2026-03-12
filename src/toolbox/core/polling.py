from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO
import time


@dataclass(frozen=True)
class ProbeResult:
    ready: bool
    detail: str | None = None


def wait_until(
    description: str,
    probe: Callable[[], ProbeResult | bool],
    *,
    timeout_seconds: float,
    interval_seconds: float,
    stream: TextIO | None = None,
) -> ProbeResult:
    deadline = time.monotonic() + timeout_seconds

    while True:
        raw_result = probe()
        result = (
            raw_result
            if isinstance(raw_result, ProbeResult)
            else ProbeResult(ready=bool(raw_result))
        )

        if result.ready:
            return result

        now = time.monotonic()
        if now >= deadline:
            detail = f" Last status: {result.detail}." if result.detail else ""
            msg = f"Timed out while waiting for {description} after {timeout_seconds:.0f}s"
            raise RuntimeError(f"{msg}: {detail}")

        time.sleep(interval_seconds)
