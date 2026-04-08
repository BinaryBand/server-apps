from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


def _load_minio_backup_module():
    import importlib.util

    script = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "minio_backup.py"
    spec = importlib.util.spec_from_file_location("minio_backup", script)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_minio_backup_imports() -> None:
    mod = _load_minio_backup_module()
    assert callable(mod.main)


def test_minio_backup_runs_compose_command() -> None:
    mod = _load_minio_backup_module()

    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch.object(sys, "argv", ["minio_backup.py"]),
    ):
        mod.main()

    cmd = captured[0]
    assert "rclone" in cmd
    assert "copy" in cmd
    assert "minio:" in cmd
    assert "pcloud:/Backups/Minio" in cmd


def test_minio_backup_scopes_to_requested_path() -> None:
    mod = _load_minio_backup_module()

    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch.object(sys, "argv", ["minio_backup.py", "/media/podcasts/morbid"]),
    ):
        mod.main()

    cmd = captured[0]
    assert "minio:media/podcasts/morbid" in cmd
    assert "pcloud:/Backups/Minio/media/podcasts/morbid" in cmd
