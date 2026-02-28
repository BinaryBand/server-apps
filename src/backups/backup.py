#!/usr/bin/env python3
"""One-time migration helper: replace Jellyfin sqlite DB inside the compose volume.

This safely backs up the existing DB (to ./.local/backups) then copies the
provided host DB file into the volume at the expected Jellyfin path.

Usage:
  python -m src.backups.backup --src "C:/path/to/jellyfin.db"

"""
import argparse
import os
import subprocess
from pathlib import Path
from datetime import datetime


def docker_volume_exists(name: str) -> bool:
    try:
        subprocess.run(
            ["docker", "volume", "inspect", name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def choose_volume(provided: str | None) -> str:
    if provided:
        if docker_volume_exists(provided):
            return provided
        raise SystemExit(f"Volume {provided} does not exist")

    # prefer JELLYFIN_NAME from env
    jelly_name = (
        os.environ.get("JELLYFIN_NAME")
        or os.environ.get("PROJECT_NAME")
        or Path.cwd().name
    )
    candidates = [
        f"{jelly_name}_data",
        f"{jelly_name}_jellyfin_data",
        "jellyfin_data",
        f"{Path.cwd().name}_jellyfin_data",
    ]
    for c in candidates:
        if docker_volume_exists(c):
            return c
    raise SystemExit("Could not find a suitable jellyfin data volume; pass --volume")


def backup_db(
    volume: str, backup_dir: Path, db_rel_path: str = "data/jellyfin.db"
) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = backup_dir / f"{volume.replace('/', '_')}_db_backup_{timestamp}.tgz"
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume}:/from",
        "-v",
        f"{str(backup_dir.resolve())}:/to",
        "alpine:3.20",
        "sh",
        "-c",
        f"cd /from && tar czf /to/{out.name} {db_rel_path} || true",
    ]
    print("Backing up existing DB to:", out)
    subprocess.run(cmd, check=True)


def copy_in_db(
    volume: str,
    src: Path,
    dest_rel: str = "data/jellyfin.db",
    puid: int = 1000,
    pgid: int = 1000,
) -> None:
    # mount src as /infile and volume as /dst then copy
    abs_src = str(src.resolve())
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume}:/dst",
        "-v",
        f"{abs_src}:/infile:ro",
        "alpine:3.20",
        "sh",
        "-c",
        f"mkdir -p /dst/$(dirname {dest_rel}) || true && cp /infile /dst/{dest_rel} && chown {puid}:{pgid} /dst/{dest_rel} || true",
    ]
    print("Copying new DB into volume...")
    subprocess.run(cmd, check=True)


def main():
    p = argparse.ArgumentParser(
        description="Replace Jellyfin DB in compose volume with a host DB file"
    )
    p.add_argument("--src", required=True, help="Path to source jellyfin.db on host")
    p.add_argument("--volume", help="Docker volume name to target (optional)")
    p.add_argument(
        "--backup-dir", default="./.local/backups", help="Host dir to store backups"
    )
    p.add_argument(
        "--puid",
        type=int,
        default=int(os.environ.get("PUID", "1000")),
        help="UID to chown the new DB to",
    )
    p.add_argument(
        "--pgid",
        type=int,
        default=int(os.environ.get("PGID", "1000")),
        help="GID to chown the new DB to",
    )
    args = p.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"Source file not found: {src}")

    vol = choose_volume(args.volume)
    print(f"Using volume: {vol}")

    backup_dir = Path(args.backup_dir)
    backup_db(vol, backup_dir)

    copy_in_db(vol, src, puid=args.puid, pgid=args.pgid)

    print(
        "Replacement complete. Please restart Jellyfin container to pick up the new DB."
    )
    print("Example: docker compose restart jellyfin")


if __name__ == "__main__":
    main()
