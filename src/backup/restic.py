from __future__ import annotations

from src.storage.compose import compose_cmd
from src.storage.volumes import storage_mount_source
from src.toolbox.core.config import restic_pcloud_remote, restic_version
from src.toolbox.docker.wrappers.rclone import rclone_sync

import subprocess
import logging

log = logging.getLogger(__name__)


PROFILE = "on-demand"
RESTIC_PCLOUD_REMOTE: str = restic_pcloud_remote()


def _restic_image() -> str:
    version: str = restic_version("latest")
    return f"restic/restic:{version}"


class ResticRunnerError(RuntimeError):
    """Raised when restic/rclone runner commands fail."""


def _restic_compose_run_command(cmd_args: list[str]) -> list[str]:
    core_args: list[str] = ["--profile", PROFILE, "run", "--rm", "--no-deps", "restic"]
    return compose_cmd(*core_args, *cmd_args)


def _ensure_restic_repo_volume_exists() -> None:
    source: str = storage_mount_source("restic_repo")

    probe: subprocess.CompletedProcess[bytes] = subprocess.run(
        ["docker", "volume", "inspect", source],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return

    cmd: list[str] = ["docker", "volume", "create", source]
    log.info("Running: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise ResticRunnerError(f"failed to ensure '{source}' exists") from err


def run_restic_command(cmd_args: list[str]) -> None:
    _ensure_restic_repo_volume_exists()
    cmd: list[str] = _restic_compose_run_command(cmd_args)

    log.info("Running: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        return_code: int = err.returncode
        command: str = " ".join(cmd)
        raise ResticRunnerError(f"restic failed with {return_code}: {command}") from err


def run_restic_command_with_output(cmd_args: list[str]) -> str:
    _ensure_restic_repo_volume_exists()
    cmd: list[str] = _restic_compose_run_command(cmd_args)

    log.info("Running: %s", " ".join(cmd))
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            cmd, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as err:
        return_code: int = err.returncode
        command: str = " ".join(cmd)
        raise ResticRunnerError(f"restic failed with {return_code}: {command}") from err

    return result.stdout


def has_restic_repo() -> bool:
    """Return True if the restic repository is already initialized.

    Mounts the backing Docker volume in a disposable alpine container and
    checks for the restic 'config' file.  This avoids both the RESTIC_PASSWORD
    requirement (restic cat config) and direct access to /var/lib/docker which
    requires root.

    A restic repository always writes a file named 'config' at the repo root
    during `restic init`.
    """
    _ensure_restic_repo_volume_exists()
    source: str = storage_mount_source("restic_repo")

    probe = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{source}:/repo:ro",
            "alpine:3.20",
            "test",
            "-f",
            "/repo/config",
        ],
        check=False,
        capture_output=True,
    )
    return probe.returncode == 0


def init_restic_repo() -> None:
    run_restic_command(["init"])


def run_backup(
    paths: list[str],
    repo: str | None = None,
    args: list[str] | None = None,
) -> None:
    cmd: list[str] = ["backup"] + paths
    if repo:
        cmd.extend(["--repo", repo])
    if args:
        cmd.extend(args)
    run_restic_command(cmd)


def push_restic_to_cloud() -> None:
    rclone_sync("restic_repo", RESTIC_PCLOUD_REMOTE)


__all__ = [
    "RESTIC_PCLOUD_REMOTE",
    "ResticRunnerError",
    "has_restic_repo",
    "init_restic_repo",
    "push_restic_to_cloud",
    "run_backup",
    "run_restic_command",
    "run_restic_command_with_output",
]
