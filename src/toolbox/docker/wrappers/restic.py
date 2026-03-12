from __future__ import annotations

from src.toolbox.docker.compose import compose_cmd
from src.toolbox.docker.volumes import storage_docker_mount_flags, storage_mount_source
from src.toolbox.docker.wrappers.rclone import rclone_sync
from src.toolbox.runtime import PROJECT_NAME
from src.toolbox.secrets import read_secret

from functools import cache
import subprocess


PROFILE = "on-demand"
RESTIC_PCLOUD_REMOTE: str = str(
    read_secret("RESTIC_PCLOUD_REMOTE", "pcloud:Backups/Restic")
)


@cache
def _restic_image() -> str:
    RESTIC_IMAGE: str = (
        read_secret("RESTIC_IMAGE")
        or f"restic/restic:{read_secret('RESTIC_VERSION', 'latest')}"
    )
    return RESTIC_IMAGE


# ResticRunnerError removed; RuntimeError used directly.
class ResticRunnerError(RuntimeError):
    """Raised when restic/rclone runner commands fail."""


def _restic_compose_run_command(cmd_args: list[str]) -> list[str]:
    core_args: list[str] = ["--profile", PROFILE, "run", "--rm", "--no-deps", "restic"]
    return compose_cmd(*core_args, *cmd_args)


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


def push_restic_to_cloud() -> None:
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


def run_restic_command(cmd_args: list[str]) -> None:
    _ensure_restic_repo_volume_exists()
    cmd = _restic_compose_run_command(cmd_args)

    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        return_code: int = err.returncode
        command: str = " ".join(cmd)
        raise ResticRunnerError(f"restic failed with {return_code}: {command}") from err


def run_restic_command_with_output(cmd_args: list[str]) -> str:
    _ensure_restic_repo_volume_exists()
    cmd = _restic_compose_run_command(cmd_args)

    print("Running:", " ".join(cmd))
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as err:
        return_code: int = err.returncode
        command: str = " ".join(cmd)
        raise ResticRunnerError(f"restic failed with {return_code}: {command}") from err

    return result.stdout


def has_restic_repo() -> bool:
    """Return True when the restic repository is already initialized."""
    try:
        run_restic_command(["snapshots"])
        return True
    except ResticRunnerError:
        return False


def init_restic_repo() -> None:
    """Initialize the restic repository in the configured /repo mount."""
    run_restic_command(["init"])


def run_backup(paths: list[str] | None = None, args: list[str] | None = None) -> None:
    backup_paths = paths or ["/backups"]
    extra_args = args or []

    run_restic_command(["backup", *backup_paths, *extra_args])
    push_restic_to_cloud()
