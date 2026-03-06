from pathlib import Path
import subprocess
from typing import List

from src.utils.compose import compose_cmd
from src.utils.secrets import read_secret


PROFILE = "on-demand"
RCLONE_IMAGE: str = str(
    read_secret("RCLONE_IMAGE")
    or f"rclone/rclone:{read_secret('RCLONE_VERSION', 'latest')}"
)
RESTIC_PCLOUD_REMOTE: str = str(
    read_secret("RESTIC_PCLOUD_REMOTE", "pcloud:Backups/Restic")
)


def push_restic_repo_to_pcloud() -> None:
    """Sync local restic repository to pCloud after backup."""
    if read_secret("RESTIC_PCLOUD_SYNC", "1") in {"0", "false", "False", "no", "NO"}:
        print("Skipping restic pCloud sync (RESTIC_PCLOUD_SYNC disabled).")
        return

    repo_root = Path(__file__).resolve().parents[2]
    local_repo = repo_root / ".local" / "restic"
    rclone_config_dir = repo_root / ".local" / "rclone"
    rclone_config_file = rclone_config_dir / "rclone.conf"

    if not rclone_config_file.exists():
        print(f"rclone config not found: {rclone_config_file}")
        return

    local_repo.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{str(local_repo.resolve())}:/repo",
        "-v",
        f"{str(rclone_config_dir.resolve())}:/config/rclone:ro",
        "-e",
        "RCLONE_CONFIG=/config/rclone/rclone.conf",
        RCLONE_IMAGE,
        "sync",
        "/repo",
        RESTIC_PCLOUD_REMOTE,
        "--progress",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_restic_command(cmd_args: List[str]) -> None:
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
    subprocess.run(cmd, check=True)


def run_backup(paths=None, restic_args=None):
    backup_paths = paths or ["/backups"]
    extra_args = restic_args or []

    try:
        run_restic_command(["snapshots"])
    except subprocess.CalledProcessError:
        print("Restic repository is not initialized yet. Running 'restic init'.")
        run_restic_command(["init"])

    run_restic_command(["backup", *backup_paths, *extra_args])
    push_restic_repo_to_pcloud()
