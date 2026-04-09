import subprocess
from subprocess import CalledProcessError, CompletedProcess
from typing import Iterable

from src.toolbox.core.config import rclone_version

_MEDIA_MOUNT_PATH = "/media"


def _rclone_image() -> str:
    version: str = rclone_version("latest")
    return f"rclone/rclone:{version}"


def _normalize_list(it: Iterable[str] | None) -> list[str]:
    return list(it) if it is not None else []


def _rclone_container_is_running(container_name: str = "rclone") -> bool:
    probe: CompletedProcess[str] = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "true"


def _docker_exec_rclone_command(command_args: list[str]) -> list[str]:
    return ["docker", "exec", "rclone", *command_args]


def _docker_exec_ok(command_args: list[str], *, text: bool = False) -> CompletedProcess[str]:
    return subprocess.run(
        _docker_exec_rclone_command(command_args),
        check=False,
        capture_output=True,
        text=text,
    )


def _mount_path_exists() -> bool:
    probe = _docker_exec_ok(["test", "-d", _MEDIA_MOUNT_PATH])
    return probe.returncode == 0


def _mount_is_active() -> bool:
    probe = _docker_exec_ok(["cat", "/proc/self/mountinfo"], text=True)
    return probe.returncode == 0 and _MEDIA_MOUNT_PATH in probe.stdout


def _command_exists(command: str) -> bool:
    probe = _docker_exec_ok(["sh", "-lc", f"command -v {command} >/dev/null 2>&1"])
    return probe.returncode == 0


def _mount_ready_for_unmount() -> bool:
    return _rclone_container_is_running() and _mount_path_exists() and _mount_is_active()


def _try_unmount_with(command: str, *args: str) -> bool:
    if not _command_exists(command):
        return False
    result = _docker_exec_ok([command, *args, _MEDIA_MOUNT_PATH])
    return result.returncode == 0


def _run_fallback_umount() -> None:
    _try_unmount_with("umount", "-l")


def _docker_run_rclone_sync_command(
    source: str,
    destination: str,
    *,
    docker_args: list[str],
    extra_args: list[str],
) -> list[str]:
    cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        *docker_args,
        _rclone_image(),
        "sync",
        source,
        destination,
        "--progress",
        *extra_args,
    ]
    return cmd


def _run_or_raise_rclone_sync(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True)
    except CalledProcessError as err:
        raise RuntimeError(f"rclone sync failed with {err.returncode}: {' '.join(cmd)}") from err


def rclone_sync(
    source: str,
    destination: str,
    *,
    docker_args: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> None:
    """Run `rclone sync` in a disposable container."""
    docker_args = _normalize_list(docker_args)
    extra_args = _normalize_list(extra_args)

    cmd = _docker_run_rclone_sync_command(
        source,
        destination,
        docker_args=docker_args,
        extra_args=extra_args,
    )
    _run_or_raise_rclone_sync(cmd)


def rclone_copy(
    source: str,
    destination: str,
    *,
    docker_args: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> None:
    """Run `rclone copy` in a disposable container (no destination deletion)."""
    docker_args = _normalize_list(docker_args)
    extra_args = _normalize_list(extra_args)

    cmd: list[str] = ["docker", "run", "--rm", *docker_args]
    cmd += [_rclone_image(), "copy", source, destination, "--progress", *extra_args]
    try:
        subprocess.run(cmd, check=True)
    except CalledProcessError as err:
        raise RuntimeError(f"rclone copy failed with {err.returncode}: {' '.join(cmd)}") from err


def rclone_lsf(
    path: str, *, docker_args: list[str] | None = None, extra_args: list[str] | None = None
) -> list[str]:
    """Run `rclone lsf --recursive --files-only` and return the file paths."""
    docker_args = _normalize_list(docker_args)
    extra_args = _normalize_list(extra_args)

    cmd: list[str] = [
        "docker",
        "run",
        "--rm",
        *docker_args,
        _rclone_image(),
        "lsf",
        path,
        "--recursive",
        "--files-only",
        *extra_args,
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except CalledProcessError as err:
        raise RuntimeError(f"rclone lsf failed with {err.returncode}: {' '.join(cmd)}") from err
    return [line for line in result.stdout.splitlines() if line]


def _try_fuse_unmount() -> None:
    """Attempt to unmount rclone FUSE mount inside the rclone container."""
    if not _mount_ready_for_unmount():
        return

    if _try_unmount_with("fusermount", "-uz"):
        return

    _run_fallback_umount()


def cleanup_media_mount() -> None:
    """Tear down the in-container rclone media mount.

    This is intentionally tolerant: stop flows should keep going even when the
    mount is already gone or unmount returns a non-zero status.
    """
    _try_fuse_unmount()


__all__ = ["rclone_sync", "rclone_copy", "rclone_lsf", "cleanup_media_mount"]
