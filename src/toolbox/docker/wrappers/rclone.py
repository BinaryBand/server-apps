from src.toolbox.core.config import rclone_version

from subprocess import CalledProcessError, CompletedProcess
from typing import Iterable

import subprocess


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


def _try_fuse_unmount() -> None:
    """Attempt to unmount rclone FUSE mount inside the rclone container."""
    if _rclone_container_is_running():
        fuse_result = subprocess.run(
            _docker_exec_rclone_command(["fusermount", "-uz", "/media/pcloud/Media"]),
            check=False,
        )
        if fuse_result.returncode != 0:
            subprocess.run(
                _docker_exec_rclone_command(["umount", "-l", "/media/pcloud/Media"]),
                check=False,
            )


def cleanup_media_mount() -> None:
    """Tear down the in-container rclone media mount.

    This is intentionally tolerant: stop flows should keep going even when the
    mount is already gone or unmount returns a non-zero status.
    """
    _try_fuse_unmount()


__all__ = ["rclone_sync", "cleanup_media_mount"]
