from pathlib import Path
import subprocess

from src.backups.db_snapshot import snapshot_sqlite


RCLONE_IMAGE = "rclone/rclone:latest"
SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}


def run(cmd):
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _is_sqlite_candidate(file_path: Path) -> bool:
    if "db-snapshots" in file_path.parts:
        return False
    if file_path.name.lower().endswith(".snapshot.db"):
        return False
    return file_path.suffix.lower() in SQLITE_EXTENSIONS


def _create_db_snapshots(backups_dir: Path) -> None:
    data_root = backups_dir / "volumes" / "jellyfin_data" / "data"
    if not data_root.exists():
        print(f"Skipping db snapshot pass; data root not found: {data_root}")
        return

    db_files = sorted(
        file_path
        for file_path in data_root.rglob("*")
        if file_path.is_file() and _is_sqlite_candidate(file_path)
    )
    if not db_files:
        print(f"No SQLite files found for snapshot pass in: {data_root}")
        return

    snapshot_root = data_root / "db-snapshots"
    print(f"Creating SQLite snapshots for {len(db_files)} file(s)...")
    failures = []
    for db_file in db_files:
        relative_parent = db_file.parent.relative_to(data_root)
        snapshot_path = snapshot_root / relative_parent / f"{db_file.name}.snapshot.db"
        try:
            snapshot_sqlite(db_file, snapshot_path)
            print(f"Snapshot created: {snapshot_path}")
        except Exception as err:
            failures.append((db_file, err))
            print(f"Snapshot failed for {db_file}: {err}")

    if failures:
        print(
            f"SQLite snapshot pass completed with {len(failures)} failure(s); continuing with gathered files."
        )


def gather_with_include_file(
    project: str, include_file: Path, backups_dir: Path, rclone_config_host: Path
):
    backups_dir = backups_dir.resolve()
    include_file = include_file.resolve()
    rclone_config_host = rclone_config_host.resolve()

    if not include_file.exists():
        raise SystemExit(f"Include file not found: {include_file}")
    if not include_file.is_file():
        raise SystemExit(f"Include path is not a file: {include_file}")

    backups_dir.mkdir(parents=True, exist_ok=True)

    jellyfin_config_vol = f"{project}_jellyfin_config"
    jellyfin_data_vol = f"{project}_jellyfin_data"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{jellyfin_config_vol}:/data/volumes/jellyfin_config:ro",
        "-v",
        f"{jellyfin_data_vol}:/data/volumes/jellyfin_data:ro",
        "-v",
        f"{str(backups_dir)}:/backups",
        "-v",
        f"{str(include_file)}:/filters/filter.txt:ro",
    ]

    if rclone_config_host.exists():
        cmd += ["-v", f"{str(rclone_config_host)}:/config/rclone:ro"]

    cmd += [
        RCLONE_IMAGE,
        "sync",
        "/data",
        "/backups",
        "--include-from",
        "/filters/filter.txt",
    ]

    run(cmd)
    _create_db_snapshots(backups_dir)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Gather selected paths from docker volumes to local backups via rclone"
    )
    parser.add_argument("--project", required=True, help="Compose project name")
    parser.add_argument("--include-file", required=True, help="Path to include file")
    parser.add_argument("--backups-dir", required=True, help="Host backups directory")
    parser.add_argument("--rclone-config-host", required=True, help="Host config")
    args = parser.parse_args()

    gather_with_include_file(
        project=args.project,
        include_file=Path(args.include_file),
        backups_dir=Path(args.backups_dir),
        rclone_config_host=Path(args.rclone_config_host),
    )


if __name__ == "__main__":
    main()
