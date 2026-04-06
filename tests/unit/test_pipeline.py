from __future__ import annotations

from unittest.mock import patch

from src.managers.pipeline import run_media_sync


def test_run_media_sync_calls_sync_with_expected_args() -> None:
    with patch("src.managers.pipeline.sync_media") as mock_sync:
        run_media_sync()

    mock_sync.assert_called_once_with(dry_run=False, delete=False)


def test_run_media_sync_is_best_effort_on_runtime_error() -> None:
    with patch(
        "src.managers.pipeline.sync_media",
        side_effect=RuntimeError("boom"),
    ):
        # Should not raise: startup pipeline must continue.
        run_media_sync()
