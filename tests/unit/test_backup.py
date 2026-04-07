from __future__ import annotations

from unittest.mock import patch, Mock
from contextlib import nullcontext

from src.orchestrators.backup import main


def test_main_runs_gather_and_restic_stages() -> None:
    """Test that backup command runs gather and restic stages in order"""
    events: list[str] = []

    def record(event: str):
        def _inner(*args, **kwargs):
            events.append(event)
            return None

        return _inner

    with (
        patch(
            "src.orchestrators.backup.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.backup.gather_stage",
            side_effect=record("gather"),
        ),
        patch(
            "src.orchestrators.backup.has_restic_repo",
            return_value=True,
        ),
        patch(
            "src.orchestrators.backup.run_backup",
            side_effect=record("restic"),
        ),
    ):
        main()

    assert "gather" in events
    assert "restic" in events


def test_main_initializes_restic_repo_if_missing() -> None:
    """Test that backup initializes restic repo if not present"""
    with (
        patch(
            "src.orchestrators.backup.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.backup.gather_stage",
            return_value=None,
        ),
        patch(
            "src.orchestrators.backup.has_restic_repo",
            return_value=False,
        ),
        patch(
            "src.orchestrators.backup.init_restic_repo",
            return_value=None,
        ),
        patch(
            "src.orchestrators.backup.run_backup",
            return_value=None,
        ),
    ):
        main()


def test_main_handles_gather_errors() -> None:
    """Test that gather stage errors stop the backup"""
    with (
        patch(
            "src.orchestrators.backup.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.backup.gather_stage",
            side_effect=RuntimeError("Gather failed: permission denied"),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "Gather failed" in str(err) or "BackupFailed" in str(err)


def test_main_handles_restic_repo_init_errors() -> None:
    """Test that restic repo initialization errors are handled"""
    from src.backup.restic import ResticRunnerError

    with (
        patch(
            "src.orchestrators.backup.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.backup.gather_stage",
            return_value=None,
        ),
        patch(
            "src.orchestrators.backup.has_restic_repo",
            return_value=False,
        ),
        patch(
            "src.orchestrators.backup.init_restic_repo",
            side_effect=ResticRunnerError("restic init failed"),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "BackupFailed" in str(err) or "restic init failed" in str(err)


def test_main_handles_backup_errors() -> None:
    """Test that restic backup stage errors are caught and reported"""
    from src.backup.restic import ResticRunnerError

    with (
        patch(
            "src.orchestrators.backup.RunbookLock",
            return_value=nullcontext(),
        ),
        patch(
            "src.orchestrators.backup.gather_stage",
            return_value=None,
        ),
        patch(
            "src.orchestrators.backup.has_restic_repo",
            return_value=True,
        ),
        patch(
            "src.orchestrators.backup.run_backup",
            side_effect=ResticRunnerError("restic backup failed: disk full"),
        ),
    ):
        try:
            main()
            raise AssertionError("Expected SystemExit")
        except SystemExit as err:
            assert "BackupFailed" in str(err) or "restic backup failed" in str(err)
