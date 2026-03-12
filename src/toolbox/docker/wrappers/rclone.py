from src.toolbox.core.runtime import media_root
from src.toolbox.core.secrets import read_secret

from subprocess import CalledProcessError, CompletedProcess
from functools import cache
from typing import Iterable
from pathlib import Path

import subprocess
import shutil
import errno
import os


@cache
def _rclone_image() -> str:
    version: str = read_secret("RCLONE_VERSION", "latest")
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


def _host_helper_command(command_args: list[str]) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--privileged",
        "--pid=host",
        "-v",
        "/:/host",
        "alpine:3.20",
        "chroot",
        "/host",
        "nsenter",
        "-t",
        "1",
        "-m",
        *command_args,
    ]


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


def _cleanup_mount_path_via_helper(mount_path: Path) -> bool:
    subprocess.run(_host_helper_command(["umount", "-l", str(mount_path)]), check=False)
    subprocess.run(_host_helper_command(["rm", "-rf", str(mount_path)]), check=False)
    result: CompletedProcess[bytes] = subprocess.run(
        _host_helper_command(["mkdir", "-p", str(mount_path)]),
        check=False,
    )
    return result.returncode == 0


def rclone_sync(
    source: str,
    destination: str,
    *,
    docker_args: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> None:
    """Run `rclone sync` inside a docker-run invocation.

    - `docker_args`: raw docker-run arguments (volume flags, -e, etc.) that are
      placed before the image name.
    - `extra_args`: additional rclone CLI arguments appended after the base
      `--progress` flag.
    """
    docker_args = _normalize_list(docker_args)
    extra_args = _normalize_list(extra_args)

    cmd = _docker_run_rclone_sync_command(
        source,
        destination,
        docker_args=docker_args,
        extra_args=extra_args,
    )

    try:
        subprocess.run(cmd, check=True)
    except CalledProcessError as err:
        return_code = err.returncode
        raise RuntimeError(f"rclone sync failed with {return_code}: {' '.join(cmd)}")


def cleanup_media_mount() -> None:
    """Tear down the host-side rclone media mount and recreate the mountpoint.

    This is intentionally tolerant: stop flows should keep going even when the
    mount is already gone or the unmount helper returns a non-zero status.
    """
    mount_path: Path = media_root() / "pcloud" / "Media"

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

    if shutil.which("fusermount") is not None:
        subprocess.run(["fusermount", "-uz", str(mount_path)], check=False)

    subprocess.run(["umount", "-l", str(mount_path)], check=False)

    mount_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        mount_path.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        if err.errno not in {errno.EEXIST, errno.ENOTCONN}:
            raise

        if _cleanup_mount_path_via_helper(mount_path):
            return

        # A stale FUSE mountpoint can remain as a broken directory entry even
        # after unmount attempts. Remove that exact path and recreate it.
        if os.path.lexists(mount_path):
            try:
                os.rmdir(mount_path)
            except OSError:
                shutil.rmtree(mount_path, ignore_errors=True)

        try:
            mount_path.mkdir(parents=True, exist_ok=True)
        except OSError as recreate_err:
            if recreate_err.errno != errno.EEXIST:
                print(
                    f"Warning: unable to recreate media mount path {mount_path}: {recreate_err}"
                )


__all__ = ["rclone_sync", "cleanup_media_mount"]
