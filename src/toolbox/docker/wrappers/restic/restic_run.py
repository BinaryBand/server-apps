from __future__ import annotations

from src.toolbox.docker.compose import compose_cmd
from src.toolbox.docker.volumes import storage_mount_source
from src.toolbox.core.config import restic_pcloud_remote, restic_version

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
    """Create the external restic repository volume when it is missing."""
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


__all__ = [
    "RESTIC_PCLOUD_REMOTE",
    "ResticRunnerError",
    "run_restic_command",
    "run_restic_command_with_output",
]
