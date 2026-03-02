import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv


_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

DEFAULT_RESTIC_EXCLUDES = [
    "/backups/restore/**",
]


def main():
    from src.backups.gather import gather_with_include_file
    from src.backups.restic_runner import run_backup

    load_dotenv()

    repo_root = Path(__file__).resolve().parents[1]
    default_backups_dir = repo_root / ".local" / "backups"
    default_include_file = repo_root / "configs" / "filters" / "backup-include.txt"
    default_rclone_config_host = repo_root / ".local" / "rclone"

    parser = argparse.ArgumentParser(
        description="Gather backup data then create a restic snapshot of that target"
    )
    parser.add_argument(
        "--project",
        default=os.getenv("PROJECT_NAME", "cloud"),
        help="Compose project name used for volume names",
    )
    parser.add_argument(
        "--include-file",
        default=str(default_include_file),
        help="Path to include file consumed by gather step",
    )
    parser.add_argument(
        "--backups-dir",
        default=str(default_backups_dir),
        help="Host backups directory for gathered data",
    )
    parser.add_argument(
        "--rclone-config-host",
        default=str(default_rclone_config_host),
        help="Host rclone config directory",
    )
    parser.add_argument(
        "--restic-target",
        default="/backups",
        help="Path inside the restic container to snapshot",
    )
    parser.add_argument(
        "--restic-arg",
        action="append",
        default=[],
        help="Additional restic argument (can be specified multiple times)",
    )
    args = parser.parse_args()

    expected_backups_dir = default_backups_dir.resolve()
    selected_backups_dir = Path(args.backups_dir).resolve()
    if (
        args.restic_target == "/backups"
        and selected_backups_dir != expected_backups_dir
    ):
        raise SystemExit(
            "--backups-dir must be ./.local/backups when --restic-target is /backups "
            "(docker compose mounts ./.local/backups to /backups in the restic container)."
        )

    gather_with_include_file(
        project=args.project,
        include_file=Path(args.include_file),
        backups_dir=Path(args.backups_dir),
        rclone_config_host=Path(args.rclone_config_host),
    )

    restic_args = list(args.restic_arg)
    if args.restic_target == "/backups":
        for pattern in DEFAULT_RESTIC_EXCLUDES:
            restic_args.extend(["--exclude", pattern])

    run_backup(paths=[args.restic_target], restic_args=restic_args)


if __name__ == "__main__":
    main()
