from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import patch

from src.toolbox.docker.wrappers.rclone import cleanup_media_mount


def _cp(cmd: list[str], returncode: int = 0, stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(cmd, returncode=returncode, stdout=stdout, stderr="")


def test_cleanup_skips_when_container_not_running() -> None:
    with patch(
        "src.toolbox.docker.wrappers.rclone.subprocess.run",
        return_value=_cp(["docker", "inspect"], returncode=1),
    ) as mock_run:
        cleanup_media_mount()

    mock_run.assert_called_once()


def test_cleanup_uses_umount_when_fusermount_missing() -> None:
    def fake_run(cmd, **kwargs):
        if cmd[:4] == ["docker", "inspect", "-f", "{{.State.Running}}"]:
            return _cp(cmd, stdout="true\n")
        if cmd[:4] == ["docker", "exec", "rclone", "test"]:
            return _cp(cmd)
        if cmd[:5] == ["docker", "exec", "rclone", "cat", "/proc/self/mountinfo"]:
            return _cp(cmd, stdout="1 1 0:1 / /media/pcloud/Media rw\n")
        if cmd[:6] == ["docker", "exec", "rclone", "sh", "-lc", "command -v fusermount >/dev/null 2>&1"]:
            return _cp(cmd, returncode=1)
        if cmd[:6] == ["docker", "exec", "rclone", "sh", "-lc", "command -v umount >/dev/null 2>&1"]:
            return _cp(cmd)
        if cmd[:4] == ["docker", "exec", "rclone", "umount"]:
            return _cp(cmd)
        raise AssertionError(f"Unexpected command: {cmd}")

    with patch("src.toolbox.docker.wrappers.rclone.subprocess.run", side_effect=fake_run):
        cleanup_media_mount()


def test_cleanup_skips_when_mount_not_active() -> None:
    def fake_run(cmd, **kwargs):
        if cmd[:4] == ["docker", "inspect", "-f", "{{.State.Running}}"]:
            return _cp(cmd, stdout="true\n")
        if cmd[:4] == ["docker", "exec", "rclone", "test"]:
            return _cp(cmd)
        if cmd[:5] == ["docker", "exec", "rclone", "cat", "/proc/self/mountinfo"]:
            return _cp(cmd, stdout="")
        raise AssertionError(f"Unexpected command: {cmd}")

    with patch("src.toolbox.docker.wrappers.rclone.subprocess.run", side_effect=fake_run):
        cleanup_media_mount()
