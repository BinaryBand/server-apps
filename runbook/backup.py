from src.backups.gather import GatherError, gather_with_include_file
from src.backups.restic_runner import (
    ResticRunnerError,
    has_restic_repository,
    initialize_restic_repository,
    run_backup,
)
from src.utils.runtime import PROJECT_NAME, repo_root
from src.utils.secrets import read_secret

from argparse import ArgumentParser, Namespace
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root()))


DEFAULT_RESTIC_EXCLUDES = ["/backups/restore/**"]


def main():
    root: Path = repo_root()
    default_include_file = root / "configs" / "backup-include.txt"
    default_backups_dir = read_secret("BACKUPS_DIR", "") or ""

    parser = ArgumentParser(description="Record a restic snapshot")
    parser.add_argument("--project", default=PROJECT_NAME)
    parser.add_argument("--include-file", default=str(default_include_file))
    parser.add_argument("--backups-dir", default=default_backups_dir)
    parser.add_argument("--restic-target", default="/backups")
    parser.add_argument("--restic-arg", action="append", default=[])
    args: Namespace = parser.parse_args()

    backups_dir = Path(args.backups_dir).resolve() if args.backups_dir else None

    try:
        print("[stage:gather] Starting gather phase")
        gather_with_include_file(
            project=args.project,
            include_file=Path(args.include_file),
            backups_dir=backups_dir,
        )
    except GatherError as err:
        raise SystemExit(f"[stage:gather] {err}") from err

    restic_args = list(args.restic_arg)

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
        run_backup(paths=[args.restic_target], restic_args=restic_args)
    except ResticRunnerError as err:
        raise SystemExit(f"[stage:restic-backup] {err}") from err

    print("[stage:complete] Backup pipeline completed")


if __name__ == "__main__":
    main()
