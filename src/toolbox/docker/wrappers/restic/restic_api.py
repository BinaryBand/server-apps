from __future__ import annotations

from src.toolbox.docker.wrappers.restic import restic_run
from src.toolbox.docker.wrappers.rclone import rclone_sync


def has_restic_repo() -> bool:
    try:
        out: str = restic_run.run_restic_command_with_output(["snapshots"])
    except restic_run.ResticRunnerError:
        return False
    return bool(out and out.strip())


def init_restic_repo() -> None:
    restic_run.run_restic_command(["init"])


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
    restic_run.run_restic_command(cmd)


def push_restic_to_cloud() -> None:
    rclone_sync("restic_repo", restic_run.RESTIC_PCLOUD_REMOTE)


__all__ = [
    "has_restic_repo",
    "init_restic_repo",
    "run_backup",
    "push_restic_to_cloud",
]
