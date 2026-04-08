from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import patch

from src.orchestrators.backup import main
from src.configuration.backup_config import BackupConfig, BatchConfig


def _empty_config() -> BackupConfig:
    return BackupConfig(batch=BatchConfig(), stream=[], compress=[])


def test_restic_push_not_called_by_default() -> None:
    with (
        patch("src.orchestrators.backup.RunbookLock", return_value=nullcontext()),
        patch("src.orchestrators.backup.BackupConfig.from_toml", return_value=_empty_config()),
        patch("src.orchestrators.backup.gather_stage", return_value=None),
        patch("src.orchestrators.backup.has_restic_repo", return_value=True),
        patch("src.orchestrators.backup.run_backup", return_value=None),
        patch("src.orchestrators.backup.push_restic_to_cloud") as mock_push,
    ):
        main()

    mock_push.assert_not_called()


def test_restic_push_called_when_enabled() -> None:
    with (
        patch("src.orchestrators.backup.RunbookLock", return_value=nullcontext()),
        patch("src.orchestrators.backup.BackupConfig.from_toml", return_value=_empty_config()),
        patch("src.orchestrators.backup.gather_stage", return_value=None),
        patch("src.orchestrators.backup.has_restic_repo", return_value=True),
        patch("src.orchestrators.backup.run_backup", return_value=None),
        patch("src.orchestrators.backup.restic_pcloud_sync_enabled", return_value=True),
        patch("src.orchestrators.backup.push_restic_to_cloud") as mock_push,
    ):
        main()

    mock_push.assert_called_once()
