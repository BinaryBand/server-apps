from pathlib import Path
import argparse
import sys

if __package__ in {None, ""}:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

DEFAULT_RESTIC_EXCLUDES = ["/backups/restore/**"]


def main():
    from src.backups.gather import gather_with_include_file
    from src.backups.restic_runner import run_backup
    from src.utils.runtime import project_name, repo_root

    root = repo_root()
    default_backups_dir = root / ".local" / "backups"
    default_include_file = root / "configs" / "backup-include.txt"
    default_rclone_config_host = root / ".local" / "rclone"

    parser = argparse.ArgumentParser(
        description="Gather backup data then create a restic snapshot of that target"
    )
    parser.add_argument(
        "--project",
        default=project_name(),
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
