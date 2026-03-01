import argparse
from dotenv import load_dotenv
from pathlib import Path
import os
import subprocess
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def main():
    from src.backups.restore import restore_snapshot

    load_dotenv()

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
        default=os.getenv("PROJECT_NAME") or _ROOT.name,
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
