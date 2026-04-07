from __future__ import annotations

from src.orchestrators.sync_media import _build_sync_cmd, _rclone_args, sync_media


def test_rclone_args_include_dry_run_flag() -> None:
    args = _rclone_args(dry_run=True)
    assert "--dry-run" in args


def test_build_sync_cmd_returns_legacy_noop_descriptor() -> None:
    cmd = _build_sync_cmd(dry_run=False, delete=False)
    assert cmd[0] == "legacy-noop"
    assert "copy" in cmd
    assert "pcloud:Media" in cmd
    assert "/media" in cmd


def test_build_sync_cmd_uses_sync_when_delete_true() -> None:
    cmd = _build_sync_cmd(dry_run=True, delete=True)
    assert cmd[:2] == ["legacy-noop", "sync"]
    assert "--dry-run" in cmd


def test_sync_media_noop_does_not_raise() -> None:
    sync_media(dry_run=False, delete=False)
