from src.backups.restore import recent_snapshots, restore_snapshot
from src.utils.runtime import repo_root

from argparse import ArgumentParser, Namespace
import sys


DEFAULT_RESTORE_TARGET = "/backups/restore"

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root()))


def main():
    parser = ArgumentParser(description="Restore a restic snapshot")
    parser.add_argument("snapshot", nargs="?", default="latest")
    parser.add_argument("--list-snapshots", action="store_true")
    parser.add_argument("--no-apply-volumes", action="store_true")
    args: Namespace = parser.parse_args()

    try:
        if args.list_snapshots:
            print("[stage:list] Listing recent snapshots")
            if output := recent_snapshots().strip():
                print(output)
            else:
                print("No snapshots found.")
            return

        print("[stage:restore] Starting snapshot restore")
        restore_snapshot(args.snapshot, DEFAULT_RESTORE_TARGET, args.no_apply_volumes)
        print("[stage:complete] Restore pipeline completed")
    except RuntimeError as err:
        raise SystemExit(f"[stage:restore] {err}") from err


if __name__ == "__main__":
    main()
