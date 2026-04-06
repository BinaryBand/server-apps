from src.toolbox.core.runtime import media_root
from src.toolbox.core.config import rclone_version

from subprocess import CalledProcessError, CompletedProcess
from typing import Iterable
from pathlib import Path

import subprocess
import shutil
import errno
import os


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


def _run_or_raise_rclone_sync(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True)
    except CalledProcessError as err:
        raise RuntimeError(f"rclone sync failed with {err.returncode}: {' '.join(cmd)}") from err


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


def _try_fuse_unmount(mount_path: Path) -> None:
    """Attempt to unmount rclone and host-level FUSE mounts."""
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


def _handle_stale_mount(mount_path: Path) -> bool:
    """Handle stale FUSE mountpoint recovery. Return True if successful."""
    if os.path.lexists(mount_path):
        try:
            os.rmdir(mount_path)
        except OSError:
            shutil.rmtree(mount_path, ignore_errors=True)

    try:
        mount_path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError as err:
        if err.errno != errno.EEXIST:
            print(f"Warning: unable to recreate media mount path {mount_path}: {err}")
        return False


def _recreate_mount_dir(mount_path: Path) -> None:
    """Recreate mount directory, recovering from stale FUSE mounts if needed."""
    try:
        mount_path.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        if err.errno not in {errno.EEXIST, errno.ENOTCONN}:
            raise

        if _cleanup_mount_path_via_helper(mount_path):
            return

        _handle_stale_mount(mount_path)


def cleanup_media_mount() -> None:
    """Tear down the host-side rclone media mount and recreate the mountpoint.

    This is intentionally tolerant: stop flows should keep going even when the
    mount is already gone or the unmount helper returns a non-zero status.
    """
    mount_path: Path = media_root() / "pcloud" / "Media"

    _try_fuse_unmount(mount_path)
    mount_path.parent.mkdir(parents=True, exist_ok=True)
    _recreate_mount_dir(mount_path)


def install_rclone_conf(local_conf_path: str | Path, volume_name: str = "rclone_config") -> None:
    """Install a prepared `rclone.conf` file into the named Docker volume.

    This uses a small alpine container to copy the provided file into
    `/config/rclone/rclone.conf` inside the volume and sets permissions to 0600.
    """
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required to install rclone.conf into a Docker volume")

    local_conf = Path(local_conf_path)
    if not local_conf.exists():
        raise FileNotFoundError(f"Local rclone.conf not found: {local_conf}")

    parent = str(local_conf.resolve().parent)
    name = local_conf.name
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume_name}:/config/rclone",
        "-v",
        f"{parent}:/staging",
        "alpine:3.20",
        "sh",
        "-c",
        f"cp /staging/{name} /config/rclone/rclone.conf && chmod 600 /config/rclone/rclone.conf",
    ]

    subprocess.run(cmd, check=True)


__all__ = ["rclone_sync", "cleanup_media_mount", "install_rclone_conf"]
