#!/usr/bin/env python3
"""Restore a local Jellyfin sqlite DB into the project's docker volume.

This is a partial implementation: it copies the provided DB into the chosen
volume path (default `data/jellyfin.db`). Optionally stops the Jellyfin
container before replace and restarts it after.
"""
import argparse
import os
import subprocess
from pathlib import Path


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
    # guess by environment / cwd
    jelly_name = (
        os.environ.get("JELLYFIN_NAME")
        or os.environ.get("PROJECT_NAME")
        or Path.cwd().name
    )
    candidates = [f"{jelly_name}_data", "jellyfin_data", f"{jelly_name}_jellyfin_data"]
    for c in candidates:
        if docker_volume_exists(c):
            return c
    raise SystemExit("Could not find a jellyfin data volume; pass --volume")


def stop_container(service_name: str):
    subprocess.run(["docker", "compose", "stop", service_name], check=False)


def start_container(service_name: str):
    subprocess.run(["docker", "compose", "start", service_name], check=False)


def copy_db_into_volume(
    volume: str,
    src: Path,
    dest_rel: str = "data/jellyfin.db",
    puid: int = 1000,
    pgid: int = 1000,
):
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
    subprocess.run(cmd, check=True)


def main():
    p = argparse.ArgumentParser(
        description="Inject a local jellyfin.db into the compose volume"
    )
    p.add_argument("--src", required=True, help="Path to local jellyfin.db to inject")
    p.add_argument("--volume", help="Target docker volume name (optional)")
    p.add_argument(
        "--service",
        default="jellyfin",
        help="Compose service name to stop/start around replace",
    )
    p.add_argument(
        "--stop", action="store_true", help="Stop the service before replacing DB"
    )
    p.add_argument(
        "--start", action="store_true", help="Start the service after replacing DB"
    )
    p.add_argument("--puid", type=int, default=int(os.environ.get("PUID", "1000")))
    p.add_argument("--pgid", type=int, default=int(os.environ.get("PGID", "1000")))
    args = p.parse_args()

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"Source DB not found: {src}")

    vol = choose_volume(args.volume)
    print(f"Target volume: {vol}")

    if args.stop:
        print(f"Stopping compose service {args.service}...")
        stop_container(args.service)

    print("Copying DB into volume...")
    copy_db_into_volume(vol, src, puid=args.puid, pgid=args.pgid)

    if args.start:
        print(f"Starting compose service {args.service}...")
        start_container(args.service)

    print("Done. Restart Jellyfin if necessary to pick up the new DB.")


if __name__ == "__main__":
    main()
