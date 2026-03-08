from __future__ import annotations

from src.utils.docker.compose import compose_cmd
from src.utils.docker.volumes import (
    storage_docker_mount_flags,
    storage_mount_source,
)
from src.utils.docker.wrappers.rclone import rclone_sync
from src.utils.runtime import PROJECT_NAME
from src.utils.secrets import read_secret

from typing import List
import subprocess


PROFILE = "on-demand"
RESTIC_PCLOUD_REMOTE: str = str(
    read_secret("RESTIC_PCLOUD_REMOTE", "pcloud:Backups/Restic")
)


class ResticRunnerError(RuntimeError):
    """Raised when restic/rclone runner commands fail."""


def _ensure_restic_repo_volume_exists() -> None:
    """Create the external restic repository volume when it is missing."""
    source = storage_mount_source(PROJECT_NAME, "restic_repo")

    probe = subprocess.run(
        ["docker", "volume", "inspect", source],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return

    cmd = ["docker", "volume", "create", source]
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise ResticRunnerError(f"failed to ensure '{source}' exists") from err


def push_restic_repo_to_pcloud() -> None:
    """Sync local restic repository to pCloud after backup."""
    if read_secret("RESTIC_PCLOUD_SYNC", "1") in {"0", "false", "False", "no", "NO"}:
        print("Skipping restic pCloud sync (RESTIC_PCLOUD_SYNC disabled).")
        return

    docker_args = storage_docker_mount_flags(PROJECT_NAME, "restic_repo", "/repo")
    docker_args += storage_docker_mount_flags(
        PROJECT_NAME, "rclone_config", "/config/rclone", read_only=True
    )
    docker_args += ["-e", "RCLONE_CONFIG=/config/rclone/rclone.conf"]

    rclone_sync("/repo", RESTIC_PCLOUD_REMOTE, docker_args=docker_args)


def run_restic_command(cmd_args: List[str]) -> None:
    _ensure_restic_repo_volume_exists()

    cmd: List[str] = compose_cmd(
        "--profile", PROFILE, "run", "--rm", "--no-deps", "restic", *cmd_args
    )
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        return_code = err.returncode
        raise ResticRunnerError(
            f"restic failed with {return_code}: {' '.join(cmd)}"
        ) from err


def has_restic_repository() -> bool:
    """Return True when the restic repository is already initialized."""
    try:
        run_restic_command(["snapshots"])
        return True
    except ResticRunnerError:
        return False


def initialize_restic_repository() -> None:
    """Initialize the restic repository in the configured /repo mount."""
    run_restic_command(["init"])


def run_backup(
    paths: List[str] | None = None, restic_args: List[str] | None = None
) -> None:
    backup_paths = paths or ["/backups"]
    extra_args = restic_args or []

    run_restic_command(["backup", *backup_paths, *extra_args])
    push_restic_repo_to_pcloud()
