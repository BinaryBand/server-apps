from __future__ import annotations

from src.utils.docker.lifecycle.runtime_post_start import run_runtime_post_start

from unittest import TestCase, main
from unittest.mock import patch


class RuntimePostStartTest(TestCase):
    def test_run_runtime_post_start_executes_in_order(self) -> None:
        events: list[str] = []

        def record(event: str):
            def _inner(*args, **kwargs):
                events.append(event)
                return None

            return _inner

        with (
            patch(
                "src.utils.docker.lifecycle.runtime_post_start.restart_jellyfin",
                side_effect=record("restart"),
            ),
            patch(
                "src.utils.docker.lifecycle.runtime_post_start.wait_for_minio_ready",
                side_effect=record("wait"),
            ),
            patch(
                "src.utils.docker.lifecycle.runtime_post_start.ensure_minio_media_bucket",
                side_effect=record("bucket"),
            ),
        ):
            run_runtime_post_start()

        self.assertEqual(events, ["restart", "wait", "bucket"])


if __name__ == "__main__":
    main()
