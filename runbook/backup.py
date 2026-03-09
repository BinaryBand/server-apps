from src.backups.gather import gather_stage
from src.utils.docker.wrappers.restic import (
    ResticRunnerError,
    has_restic_repository,
    initialize_restic_repository,
    run_backup,
)
from src.utils.runtime import PROJECT_NAME, repo_root

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root()))


DEFAULT_RESTIC_EXCLUDES = ["/backups/restore/**"]
DEFAULT_RESTIC_TARGET = "/backups"


def main():
    root: Path = repo_root()
    include_file = root / "configs" / "backup-include.txt"

    try:
        print("[stage:gather] Starting gather phase")
        gather_stage(project=PROJECT_NAME, include_file=include_file)
    except RuntimeError as err:
        raise SystemExit(f"[stage:gather] {err}") from err

    restic_args = []
    if DEFAULT_RESTIC_TARGET == "/backups":
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
        run_backup(paths=[DEFAULT_RESTIC_TARGET], args=restic_args)
    except ResticRunnerError as err:
        raise SystemExit(f"[stage:restic-backup] {err}") from err

    print("[stage:complete] Backup pipeline completed")


if __name__ == "__main__":
    main()
