import subprocess
import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def main():
    from src.backups.restore import restore_snapshot, RestoreRunnerError
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
    parser.add_argument(
        "--allow-destructive-apply",
        action="store_true",
        help=(
            "Acknowledge destructive sync behavior when applying restored data "
            "back into runtime targets."
        ),
    )
    args = parser.parse_args()

    try:
        print("[stage:restore] Starting snapshot restore")
        restore_snapshot(
            args.snapshot,
            args.target,
            project=args.project,
            no_apply_volumes=args.no_apply_volumes,
            allow_destructive_apply=args.allow_destructive_apply,
        )
        print("[stage:complete] Restore pipeline completed")
    except RestoreRunnerError as err:
        raise SystemExit(f"[stage:restore] {err}") from err


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Restore interrupted (Ctrl+C).")
        sys.exit(130)
