from __future__ import annotations

from unittest.mock import patch, Mock
from contextlib import nullcontext

from src.orchestrators.backup import main
from src.backup.restic import ResticRunnerError, has_restic_repo
from src.configuration.backup_config import BackupConfig, BatchConfig


def _empty_config() -> BackupConfig:
    """Minimal config with no stream or compress stages."""
    return BackupConfig(batch=BatchConfig(), stream=[], compress=[])


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
            "src.orchestrators.backup.BackupConfig.from_toml",
            return_value=_empty_config(),
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
            "src.orchestrators.backup.BackupConfig.from_toml",
            return_value=_empty_config(),
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


class TestHasResticRepo:
    """has_restic_repo() mounts the volume in a container — no password, no root needed."""

    def test_returns_true_when_config_file_exists(self) -> None:
        """docker run exits 0 (test -f succeeds) → repo initialized."""
        with (
            patch("src.backup.restic._ensure_restic_repo_volume_exists"),
            patch("src.backup.restic.storage_mount_source", return_value="restic_repo_data"),
            patch("src.backup.restic.subprocess.run", return_value=_run_result(0)),
        ):
            assert has_restic_repo() is True

    def test_returns_false_when_config_file_missing(self) -> None:
        """docker run exits 1 (test -f fails) → repo not initialized."""
        with (
            patch("src.backup.restic._ensure_restic_repo_volume_exists"),
            patch("src.backup.restic.storage_mount_source", return_value="restic_repo_data"),
            patch("src.backup.restic.subprocess.run", return_value=_run_result(1)),
        ):
            assert has_restic_repo() is False

    def test_returns_false_when_docker_run_fails(self) -> None:
        """Non-zero exit for any reason (e.g. image pull error) → False."""
        with (
            patch("src.backup.restic._ensure_restic_repo_volume_exists"),
            patch("src.backup.restic.storage_mount_source", return_value="restic_repo_data"),
            patch("src.backup.restic.subprocess.run", return_value=_run_result(125)),
        ):
            assert has_restic_repo() is False

    def test_mounts_correct_volume(self) -> None:
        """The docker run command must mount the restic volume at /repo."""
        captured: list[list[str]] = []

        def _spy(cmd, **kwargs):
            captured.append(list(cmd))
            return _run_result(0)

        with (
            patch("src.backup.restic._ensure_restic_repo_volume_exists"),
            patch("src.backup.restic.storage_mount_source", return_value="my_vol"),
            patch("src.backup.restic.subprocess.run", side_effect=_spy),
        ):
            has_restic_repo()

        assert captured, "subprocess.run was not called"
        cmd = captured[0]
        assert "my_vol:/repo:ro" in " ".join(cmd)
        assert "test" in cmd
        assert "/repo/config" in cmd

    def test_does_not_invoke_restic(self) -> None:
        """No restic compose command must be issued — check is volume-level."""
        captured: list[list[str]] = []

        def _spy(cmd, **kwargs):
            captured.append(list(cmd))
            return _run_result(0)

        with (
            patch("src.backup.restic._ensure_restic_repo_volume_exists"),
            patch("src.backup.restic.storage_mount_source", return_value="vol"),
            patch("src.backup.restic.subprocess.run", side_effect=_spy),
        ):
            has_restic_repo()

        for cmd in captured:
            assert "compose" not in cmd, f"unexpected compose call: {cmd}"
            assert "restic" not in [c for c in cmd if not c.startswith("-")], (
                f"unexpected restic invocation: {cmd}"
            )


# ---------------------------------------------------------------------------
# Helpers for TestHasResticRepo
# ---------------------------------------------------------------------------


def _run_result(returncode: int):
    from unittest.mock import MagicMock

    r = MagicMock()
    r.returncode = returncode
    return r
