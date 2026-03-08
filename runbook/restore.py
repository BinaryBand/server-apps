from src.backups.restore import RestoreRunnerError, restore_snapshot
from src.utils.runtime import repo_root

from argparse import ArgumentParser, Namespace
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root()))


def main():
    parser = ArgumentParser(description="Restore a restic snapshot into a target path")
    parser.add_argument("snapshot", nargs="?", default="latest")
    parser.add_argument("target", nargs="?", default="/backups/restore")
    parser.add_argument("--no-apply-volumes", action="store_true")
    args: Namespace = parser.parse_args()

    try:
        print("[stage:restore] Starting snapshot restore")
        restore_snapshot(args.snapshot, args.target, args.no_apply_volumes)
        print("[stage:complete] Restore pipeline completed")
    except RestoreRunnerError as err:
        raise SystemExit(f"[stage:restore] {err}") from err


if __name__ == "__main__":
    main()
