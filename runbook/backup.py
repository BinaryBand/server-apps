from pathlib import Path
import argparse
import sys
from datetime import datetime, timezone

if __package__ in {None, ""}:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

DEFAULT_RESTIC_EXCLUDES = ["/backups/restore/**"]


def main():
    from src.backups.gather import gather_with_include_file, GatherError
    from src.backups.restic_runner import (
        ResticRunnerError,
        has_restic_repository,
        initialize_restic_repository,
        run_backup,
    )
    from src.utils.runtime import project_name, repo_root
    from src.utils.secrets import read_secret

    root = repo_root()
    default_include_file = root / "configs" / "backup-include.txt"
    default_backups_dir = read_secret("BACKUPS_DIR", "") or ""
    default_rclone_config_host = read_secret("RCLONE_CONFIG_DIR") or str(
        root / ".local" / "rclone"
    )

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
        default=default_backups_dir,
        help=(
            "Host backups directory override. Leave empty to use named volume "
            "${PROJECT_NAME}_backups mounted at /backups."
        ),
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
    parser.add_argument(
        "--backup-tag",
        default="",
        help=(
            "Optional backup tag. Defaults to UTC timestamp tag "
            "(backup-YYYYMMDDTHHMMSSZ)."
        ),
    )
    args = parser.parse_args()

    backups_dir = Path(args.backups_dir).resolve() if args.backups_dir else None

    try:
        print("[stage:gather] Starting gather phase")
        gather_with_include_file(
            project=args.project,
            include_file=Path(args.include_file),
            backups_dir=backups_dir,
            rclone_config_host=Path(args.rclone_config_host),
        )
    except GatherError as err:
        raise SystemExit(f"[stage:gather] {err}") from err

    restic_args = list(args.restic_arg)
    backup_tag = args.backup_tag or datetime.now(timezone.utc).strftime(
        "backup-%Y%m%dT%H%M%SZ"
    )
    restic_args.extend(["--tag", backup_tag])

    if args.restic_target == "/backups":
        for pattern in DEFAULT_RESTIC_EXCLUDES:
            restic_args.extend(["--exclude", pattern])

    print("[stage:restic] Checking repository state")
    if not has_restic_repository():
        print("[stage:restic-init] Repository not initialized; running init")
        try:
            initialize_restic_repository()
        except ResticRunnerError as err:
            raise SystemExit(f"[stage:restic-init] {err}") from err

    try:
        print(f"[stage:restic-backup] Running backup with tag '{backup_tag}'")
        run_backup(paths=[args.restic_target], restic_args=restic_args)
    except ResticRunnerError as err:
        raise SystemExit(f"[stage:restic-backup] {err}") from err

    print("[stage:complete] Backup pipeline completed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Backup interrupted (Ctrl+C).")
        sys.exit(130)
