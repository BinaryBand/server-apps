from __future__ import annotations

from argparse import ArgumentParser, Namespace


def _parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Legacy media sync command (mount-only mode does not copy media)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing destination files",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete destination files missing in source (strict mirror)",
    )
    return parser.parse_args()


def _require_storage_key(name: str) -> None:
    # Kept for compatibility with existing imports/tests; mount-only mode has
    # no storage-key dependency.
    _ = name


def _rclone_args(*, dry_run: bool) -> list[str]:
    args: list[str] = []
    if dry_run:
        args.append("--dry-run")
    return args


def _build_sync_cmd(*, dry_run: bool, delete: bool) -> list[str]:
    operation = "sync" if delete else "copy"
    cmd: list[str] = ["legacy-noop", operation, "pcloud:Media", "/media"]
    cmd.extend(_rclone_args(dry_run=dry_run))
    return cmd


def sync_media(*, dry_run: bool, delete: bool) -> None:
    _ = _build_sync_cmd(dry_run=dry_run, delete=delete)
    print("[media-sync] mount-only mode enabled; skipping media copy")


def main() -> None:
    args = _parse_args()
    sync_media(dry_run=args.dry_run, delete=args.delete)


if __name__ == "__main__":
    main()
