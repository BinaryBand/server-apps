#!/usr/bin/env python3
"""Create host-level SQL dumps of SQLite DB files stored in a Docker volume.

This script tars the specified Docker volume to a host output directory,
extracts it, finds SQLite files (*.db, *.sqlite) and writes SQL dumps using
Python's sqlite3 iterdump to `output_dir/dumps/<relative_path>.sql`.

Usage:
  python -m src.backups.snapshot --volume cloud_jellyfin_data --output ./.local/cloud_jellyfin_snapshot

"""
import argparse
import os
import subprocess
import tarfile
import sqlite3
from pathlib import Path
import shutil


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


def create_volume_archive(volume: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    abs_out = str(out_dir.resolve())
    archive_path = out_dir / "volume.tar.gz"
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume}:/src",
        "-v",
        f"{abs_out}:/out",
        "alpine:3.20",
        "sh",
        "-c",
        "cd /src && tar czf /out/volume.tar.gz .",
    ]
    subprocess.run(cmd, check=True)
    return archive_path


def create_selective_copy(volume: str, out_dir: Path) -> Path:
    """Copy only sqlite-like files from the volume into out_dir/_selective and
    return the path to that directory.
    """
    abs_out = str(out_dir.resolve())
    target_dir = out_dir / "_selective"
    # Ensure clean target
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Use a small shell loop inside an alpine container to copy matching files.
    # This approach is simple and avoids archiving the whole volume.
    sh_cmd = (
        "cd /src && "
        r'for f in $(find . -type f \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \)); do '
        r'mkdir -p /out/_selective/$(dirname "$f") && cp -a "$f" /out/_selective/$f; done'
    )
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume}:/src",
        "-v",
        f"{abs_out}:/out",
        "alpine:3.20",
        "sh",
        "-c",
        sh_cmd,
    ]
    subprocess.run(cmd, check=True)
    return target_dir


def extract_archive(archive: Path, extract_to: Path):
    extract_to.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(path=str(extract_to))


def find_sqlite_files(root: Path):
    exts = {".db", ".sqlite", ".sqlite3"}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def dump_sqlite(db_path: Path, out_sql: Path):
    out_sql.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        with out_sql.open("w", encoding="utf-8") as fh:
            for line in conn.iterdump():
                fh.write(f"{line}\n")
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser(
        description="Snapshot SQLite DB files from a Docker volume and dump SQL to host"
    )
    p.add_argument(
        "--volume",
        default=None,
        help="Docker volume name containing Jellyfin data (default: try project prefix then 'cloud_jellyfin_data')",
    )
    p.add_argument(
        "--output",
        default="./.local/cloud_jellyfin_snapshot",
        help="Host output directory",
    )
    p.add_argument(
        "--project",
        default=None,
        help="Compose project name (used to guess volume name)",
    )
    p.add_argument(
        "--keep-archive",
        action="store_true",
        help="Keep the intermediate volume tar.gz",
    )

    args = p.parse_args()
    out_dir = Path(args.output)

    # Determine volume name
    volume = args.volume
    if not volume:
        project = args.project or os.environ.get("PROJECT_NAME") or Path.cwd().name
        candidate = f"{project}_cloud_jellyfin_data"
        if docker_volume_exists(candidate):
            volume = candidate
        elif docker_volume_exists("cloud_jellyfin_data"):
            volume = "cloud_jellyfin_data"
        else:
            raise SystemExit("Could not find data volume; please pass --volume <name>")

    print(f"Using docker volume: {volume}")

    # Instead of archiving and dumping, copy only raw `.db` files from the
    # volume into `output/_selective` and skip SQL dumps.
    try:
        target = create_selective_copy(volume, out_dir)
        print(f"Copied .db files to: {target}")
        # report files copied
        files = list(target.rglob("*.db"))
        for f in files:
            print(f" - {f.relative_to(out_dir)}")
        print(f"Copied {len(files)} .db files")
    finally:
        # remove intermediate archive if it somehow exists (compat)
        if not args.keep_archive:
            try:
                (out_dir / "volume.tar.gz").unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
