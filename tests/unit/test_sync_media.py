from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from src.orchestrators.sync_media import _build_sync_cmd, _rsync_args, sync_media


def test_rsync_args_include_dry_run_and_delete_flags() -> None:
    args = _rsync_args(dry_run=True, delete=True)
    assert "--dry-run" in args
    assert "--delete" in args


def test_build_sync_cmd_uses_expected_volume_mounts_and_paths() -> None:
    with patch(
        "src.orchestrators.sync_media.storage_mount_source",
        side_effect=["media_source_data", "media_read_data"],
    ):
        cmd = _build_sync_cmd(dry_run=False, delete=False)

    assert cmd[:3] == ["docker", "run", "--rm"]
    assert "media_source_data:/src:ro" in cmd
    assert "media_read_data:/dst" in cmd
    assert "alpine:3.20" in cmd

    shell_cmd = cmd[-1]
    assert "rsync -a --human-readable --info=progress2 --stats /src/ /dst/" in shell_cmd
    assert "/src/pcloud/Media" not in shell_cmd


def test_build_sync_cmd_adds_dry_run_and_delete_to_rsync_command() -> None:
    with patch(
        "src.orchestrators.sync_media.storage_mount_source",
        side_effect=["media_source_data", "media_read_data"],
    ):
        cmd = _build_sync_cmd(dry_run=True, delete=True)

    shell_cmd = cmd[-1]
    assert "--dry-run" in shell_cmd
    assert "--delete" in shell_cmd


def test_sync_media_raises_runtime_error_on_non_zero_return() -> None:
    with (
        patch(
            "src.orchestrators.sync_media.storage_mount_source",
            side_effect=["media_source_data", "media_read_data"],
        ),
        patch(
            "src.orchestrators.sync_media.subprocess.run",
            return_value=CompletedProcess(args=["docker"], returncode=23),
        ),
    ):
        with pytest.raises(RuntimeError) as err:
            sync_media(dry_run=False, delete=False)

    assert "Media sync failed with code 23" in str(err.value)


def test_sync_media_succeeds_on_zero_return() -> None:
    with (
        patch(
            "src.orchestrators.sync_media.storage_mount_source",
            side_effect=["media_source_data", "media_read_data"],
        ),
        patch(
            "src.orchestrators.sync_media.subprocess.run",
            return_value=CompletedProcess(args=["docker"], returncode=0),
        ),
    ):
        sync_media(dry_run=False, delete=False)
