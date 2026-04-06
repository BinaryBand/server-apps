from __future__ import annotations

from src.configuration.storage_manifest import STORAGE_TARGETS
from src.toolbox.docker.volumes import storage_mount_source

from argparse import ArgumentParser, Namespace
import subprocess


def _parse_args() -> Namespace:
    parser = ArgumentParser(
        description="Sync media from rclone-mounted volume to reader volume"
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
    if name not in STORAGE_TARGETS:
        raise RuntimeError(f"Missing storage target key: {name}")


def _rsync_args(*, dry_run: bool, delete: bool) -> list[str]:
    args: list[str] = ["-a", "--human-readable", "--info=progress2", "--stats"]
    if dry_run:
        args.append("--dry-run")
    if delete:
        args.append("--delete")
    return args


def _build_sync_cmd(*, dry_run: bool, delete: bool) -> list[str]:
    _require_storage_key("media_source")
    _require_storage_key("media_read")

    source = storage_mount_source("media_source")
    destination = storage_mount_source("media_read")
    rsync_opts = " ".join(_rsync_args(dry_run=dry_run, delete=delete))

    shell_cmd = " && ".join(
        [
            "apk add --no-cache rsync >/dev/null",
            "mkdir -p /dst",
            f"rsync {rsync_opts} /src/ /dst/",
        ]
    )

    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{source}:/src:ro",
        "-v",
        f"{destination}:/dst",
        "alpine:3.20",
        "sh",
        "-lc",
        shell_cmd,
    ]


def sync_media(*, dry_run: bool, delete: bool) -> None:
    cmd = _build_sync_cmd(dry_run=dry_run, delete=delete)
    print("[media-sync] Running rsync from media_source -> media_read")
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Media sync failed with code {proc.returncode}")


def main() -> None:
    args = _parse_args()
    sync_media(dry_run=args.dry_run, delete=args.delete)


if __name__ == "__main__":
    main()
