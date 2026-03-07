from pathlib import Path
import subprocess

from src.utils.secrets import read_secret
from src.utils import volumes as volutils


RCLONE_IMAGE: str = (
    read_secret("RCLONE_IMAGE")
    or f"rclone/rclone:{read_secret('RCLONE_VERSION', 'latest')}"
)


class GatherError(RuntimeError):
    """Raised when gather operations fail."""


def run(cmd):
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise GatherError(
            f"Gather command failed with exit code {err.returncode}: {' '.join(cmd)}"
        ) from err


def gather_with_include_file(
    project: str,
    include_file: Path,
    backups_dir: Path | None,
):
    include_file = include_file.resolve()
    backups_dir = backups_dir.resolve() if backups_dir else None

    if not include_file.exists():
        raise GatherError(f"Include file not found: {include_file}")
    if not include_file.is_file():
        raise GatherError(f"Include path is not a file: {include_file}")

    if backups_dir:
        backups_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["docker", "run", "--rm"]
    cmd += volutils.rclone_docker_volume_flags(project)

    if backups_dir:
        cmd += ["-v", f"{str(backups_dir)}:/backups"]
    else:
        cmd += volutils.storage_docker_mount_flags(project, "backups", "/backups")

    cmd += ["-v", f"{str(include_file)}:/filters/backup-include.txt:ro"]
    cmd += volutils.storage_docker_mount_flags(
        project,
        "rclone_config",
        "/config/rclone",
        read_only=True,
    )

    cmd += [RCLONE_IMAGE, "sync", "/data", "/backups", "--progress", "--include-from", "/filters/backup-include.txt"]

    run(cmd)
