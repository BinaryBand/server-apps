import argparse
from dotenv import load_dotenv
from pathlib import Path
import subprocess
import sys

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def main():
    from src.backups.restic_runner import run_restic_command

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
    args = parser.parse_args()

    run_restic_command(["restore", args.snapshot, "--target", args.target])


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print("Command failed:", e)
        sys.exit(1)
