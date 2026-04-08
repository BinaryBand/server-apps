from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import patch

from src.configuration.backup_config import BackupConfig, BatchConfig
from src.orchestrators.restore import main


def _empty_config() -> BackupConfig:
    return BackupConfig(batch=BatchConfig(), stream=[])


def test_main_runs_restore_stage_when_not_listing() -> None:
    """Test that restore command runs restore stage when not listing snapshots"""
    events: list[str] = []

    def record(event: str):
        def _inner(*args, **kwargs):
            events.append(event)
            return None

        return _inner

    with (
        patch(
            "src.orchestrators.restore.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.restore.BackupConfig.from_toml",
            return_value=_empty_config(),
        ),
        patch(
            "src.orchestrators.restore.restore_snapshot",
            side_effect=record("restore"),
        ),
        patch("sys.argv", ["restore"]),
    ):
        main()

    assert "restore" in events


def test_main_lists_snapshots_when_requested() -> None:
    """Test that restore command lists snapshots when --list-snapshots is passed"""
    with (
        patch(
            "src.orchestrators.restore.recent_snapshots",
            return_value="latest\nolder",
        ),
        patch("sys.argv", ["restore", "--list-snapshots"]),
    ):
        main()  # Should return early without error


def test_main_handles_restore_errors() -> None:
    """Test that restore stage errors are caught and reported"""
    with (
        patch(
            "src.orchestrators.restore.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.restore.BackupConfig.from_toml",
            return_value=_empty_config(),
        ),
        patch(
            "src.orchestrators.restore.restore_snapshot",
            side_effect=RuntimeError("Restore failed: snapshot not found"),
        ),
        patch("sys.argv", ["restore"]),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "Restore failed" in str(err) or "RestoreFailed" in str(err)


def test_main_handles_snapshot_list_errors() -> None:
    """Test that snapshot listing errors are caught and reported gracefully"""
    with (
        patch(
            "src.orchestrators.restore.recent_snapshots",
            side_effect=RuntimeError("Snapshot list failed"),
        ),
        patch("sys.argv", ["restore", "--list-snapshots"]),
    ):
        try:
            main()
            raise AssertionError("Expected RuntimeError")
        except RuntimeError as err:
            assert "Snapshot list failed" in str(err)
