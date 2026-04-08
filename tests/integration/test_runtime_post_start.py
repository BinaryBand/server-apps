from __future__ import annotations

from unittest.mock import patch

from src.observability.post_start import run_runtime_post_start


def test_run_runtime_post_start_executes_in_order() -> None:
    events: list[str] = []

    def record(event: str):
        def _inner(*args, **kwargs):
            events.append(event)
            return None

        return _inner

    with (
        patch(
            "src.observability.post_start.restart_jellyfin",
            side_effect=record("restart"),
        ),
    ):
        run_runtime_post_start()

    assert events == ["restart"]
