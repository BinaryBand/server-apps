from pathlib import Path
import subprocess
from typing import List

from src.utils.compose import compose_cmd
from src.utils.secrets import read_secret
from src.utils import volumes as volutils


PROFILE = "on-demand"
RCLONE_IMAGE: str = str(
    read_secret("RCLONE_IMAGE")
    or f"rclone/rclone:{read_secret('RCLONE_VERSION', 'latest')}"
)
RESTIC_PCLOUD_REMOTE: str = str(
    read_secret("RESTIC_PCLOUD_REMOTE", "pcloud:Backups/Restic")
)


class ResticRunnerError(RuntimeError):
    """Raised when restic/rclone runner commands fail."""


def _ensure_external_backups_volume_exists() -> None:
    """Create the external backups volume in named-volume mode if missing."""
    repo_root = Path(__file__).resolve().parents[2]
    project = read_secret("PROJECT_NAME") or repo_root.name
    source, is_host = volutils.storage_mount_source(project, "backups")
    if is_host:
        return

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
        raise ResticRunnerError(
            f"failed to ensure backups volume '{source}' exists (exit {err.returncode})"
        ) from err


def push_restic_repo_to_pcloud() -> None:
    """Sync local restic repository to pCloud after backup."""
    if read_secret("RESTIC_PCLOUD_SYNC", "1") in {"0", "false", "False", "no", "NO"}:
        print("Skipping restic pCloud sync (RESTIC_PCLOUD_SYNC disabled).")
        return

    repo_root = Path(__file__).resolve().parents[2]
    project = read_secret("PROJECT_NAME") or repo_root.name

    cmd = [
        "docker",
        "run",
        "--rm",
        *volutils.storage_docker_mount_flags(project, "restic_repo", "/repo"),
        *volutils.storage_docker_mount_flags(
            project,
            "rclone_config",
            "/config/rclone",
            read_only=True,
        ),
        "-e",
        "RCLONE_CONFIG=/config/rclone/rclone.conf",
        RCLONE_IMAGE,
        "sync",
        "/repo",
        RESTIC_PCLOUD_REMOTE,
        "--progress",
    ]
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise ResticRunnerError(
            f"pCloud sync failed with exit code {err.returncode}: {' '.join(cmd)}"
        ) from err


def run_restic_command(cmd_args: List[str]) -> None:
    _ensure_external_backups_volume_exists()

    cmd: List[str] = compose_cmd(
        "--profile",
        PROFILE,
        "run",
        "--rm",
        "--no-deps",
        "restic",
        *cmd_args,
    )
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise ResticRunnerError(
            f"restic command failed with exit code {err.returncode}: {' '.join(cmd)}"
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


def run_backup(paths=None, restic_args=None):
    backup_paths = paths or ["/backups"]
    extra_args = restic_args or []

    run_restic_command(["backup", *backup_paths, *extra_args])
    push_restic_repo_to_pcloud()
