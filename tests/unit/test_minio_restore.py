from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


def _load_minio_restore_module():
    import importlib.util

    script = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "minio_restore.py"
    spec = importlib.util.spec_from_file_location("minio_restore", script)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_minio_restore_imports() -> None:
    """Ensure minio_restore.py can be imported without errors."""
    mod = _load_minio_restore_module()
    assert callable(mod.main)


def test_minio_restore_runs_compose_command(monkeypatch: object) -> None:
    """main() builds a compose command and passes it to subprocess.run."""
    mod = _load_minio_restore_module()

    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch.object(sys, "argv", ["minio_restore.py"]),
    ):
        mod.main()

    assert captured, "subprocess.run was not called"
    cmd = captured[0]
    assert "rclone" in cmd
    assert "sync" in cmd
    assert "pcloud:/Backups/Minio" in cmd
    assert "minio:" in cmd


def test_minio_restore_scopes_to_requested_path() -> None:
    mod = _load_minio_restore_module()

    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch.object(sys, "argv", ["minio_restore.py", "/media/podcasts/morbid"]),
    ):
        mod.main()

    cmd = captured[0]
    assert "pcloud:/Backups/Minio/media/podcasts/morbid" in cmd
    assert "minio:media/podcasts/morbid" in cmd


def test_minio_restore_applies_include_exclude_filters() -> None:
    mod = _load_minio_restore_module()

    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch.object(
            sys,
            "argv",
            [
                "minio_restore.py",
                "--include",
                "/media/podcasts",
                "--exclude",
                "/media/podcasts/morbid",
                "--exclude",
                "/media/podcasts/necronomipod",
            ],
        ),
    ):
        mod.main()

    cmd = captured[0]
    assert "--filter" in cmd
    assert "- media/podcasts/morbid/**" in cmd
    assert "- media/podcasts/necronomipod/**" in cmd
    assert "+ media/podcasts/**" in cmd
    assert "- **" in cmd


def test_minio_restore_exclude_only_uses_filter_without_catch_all() -> None:
    mod = _load_minio_restore_module()

    captured: list = []

    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    with (
        patch("subprocess.run", side_effect=fake_run),
        patch.object(
            sys,
            "argv",
            [
                "minio_restore.py",
                "--exclude",
                "/media/podcasts/necronomipod",
            ],
        ),
    ):
        mod.main()

    cmd = captured[0]
    assert "--filter" in cmd
    assert "- media/podcasts/necronomipod/**" in cmd
    assert "- **" not in cmd
