import subprocess
import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

from runbook._bootstrap import ensure_repo_on_syspath


ensure_repo_on_syspath()


def main():
    from src.backups.restore import restore_snapshot
    from src.utils.runtime import project_name

    parser = argparse.ArgumentParser(
        description="Restore a restic snapshot into a target path"
    )
    parser.add_argument(
        "snapshot",
        nargs="?",
        default="latest",
        help="Snapshot ID to restore (default: latest)",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="/backups/restore",
        help="Restore target path inside the restic container",
    )
    parser.add_argument(
        "--project",
        default=project_name(),
        help="Compose project name used for docker volume names",
    )
    parser.add_argument(
        "--no-apply-volumes",
        action="store_true",
        help="Only restore files to target path; do not copy restored data into docker volumes",
    )
    args = parser.parse_args()

    restore_snapshot(
        args.snapshot,
        args.target,
        project=args.project,
        no_apply_volumes=args.no_apply_volumes,
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        if e.returncode == 130:
            print("Restore interrupted (Ctrl+C). No further action taken.")
            sys.exit(130)
        print("Command failed:", e)
        sys.exit(e.returncode or 1)
    except KeyboardInterrupt:
        print("Restore interrupted (Ctrl+C).")
        sys.exit(130)
