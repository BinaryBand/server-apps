from __future__ import annotations

from src.toolbox.docker.post_start import run_runtime_post_start

from unittest.mock import patch


def test_run_runtime_post_start_executes_in_order() -> None:
    events: list[str] = []

    def record(event: str):
        def _inner(*args, **kwargs):
            events.append(event)
            return None

        return _inner

    with (
        patch(
            "src.toolbox.docker.post_start.restart_jellyfin",
            side_effect=record("restart"),
        ),
        patch(
            "src.toolbox.docker.post_start.wait_for_minio_ready",
            side_effect=record("wait"),
        ),
        patch(
            "src.toolbox.docker.post_start.ensure_minio_media_bucket",
            side_effect=record("bucket"),
        ),
    ):
        run_runtime_post_start()

    assert events == ["restart", "wait", "bucket"]

