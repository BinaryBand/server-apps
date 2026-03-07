import sys
from pathlib import Path

# 1. db_snapshot.py
db_snapshot_content = """import sqlite3
from pathlib import Path
from src.utils import volumes as volutils

SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}

class DbSnapshotError(RuntimeError):
    \"\"\"Raised when SQLite snapshot operations fail.\"\"\"

def snapshot_sqlite(source_path: Path, output_path: Path) -> None:
    src = source_path.resolve()
    dst = output_path.resolve()

    if not src.exists() or not src.is_file():
        raise DbSnapshotError(f"Source SQLite file not found: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    src_uri = f"file:{src.as_posix()}?mode=ro"
    with sqlite3.connect(src_uri, uri=True) as source_conn:
        source_conn.execute("PRAGMA busy_timeout = 15000")
        with sqlite3.connect(str(dst)) as dest_conn:
            source_conn.backup(dest_conn)
            dest_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

def _is_sqlite_candidate(file_path: Path) -> bool:
    if "db-snapshots" in file_path.parts:
        return False
    if file_path.name.lower().endswith(".snapshot.db"):
        return False
    return file_path.suffix.lower() in SQLITE_EXTENSIONS

def _create_db_snapshots_for_volume(volume_dir: Path) -> None:
    data_subdir = volume_dir / "data"
    if data_subdir.exists():
        data_root = data_subdir
    else:
        data_root = volume_dir

    db_files = sorted(
        file_path
        for file_path in data_root.rglob("*")
        if file_path.is_file() and _is_sqlite_candidate(file_path)
    )
    if not db_files:
        return

    snapshot_root = data_root / "db-snapshots"
    print(f"Creating SQLite snapshots for {len(db_files)} file(s) in {volume_dir.name}...")
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
        print(f"SQLite snapshot pass completed with {len(failures)} failure(s).")

def create_db_snapshots(backups_dir: Path) -> None:
    volume_dirs = volutils.gathered_volume_dirs(backups_dir)
    if not volume_dirs:
        print(f"Skipping db snapshot pass; no volumes found under: {backups_dir / 'volumes'}")
        return

    for volume_dir in volume_dirs:
        _create_db_snapshots_for_volume(volume_dir)
"""

Path("src/backups/db_snapshot.py").write_text(db_snapshot_content)

# 2. gather.py
gather_content = """from pathlib import Path
import subprocess

from src.utils.secrets import read_secret
from src.utils import volumes as volutils


RCLONE_IMAGE: str = (
    read_secret("RCLONE_IMAGE")
    or f"rclone/rclone:{read_secret('RCLONE_VERSION', 'latest')}"
)

class GatherError(RuntimeError):
    \"\"\"Raised when gather operations fail.\"\"\"

def run(cmd):
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise GatherError(
            f"Gather command failed with exit code {err.returncode}: {' '.join(cmd)}"
        ) from err


def gather_with_include_file(
    project: str,
    include_file: Path,
    backups_dir: Path | None,
    rclone_config_host: Path,
):
    include_file = include_file.resolve()
    rclone_config_host = rclone_config_host.resolve()
    backups_dir = backups_dir.resolve() if backups_dir else None

    if not include_file.exists():
        raise GatherError(f"Include file not found: {include_file}")
    if not include_file.is_file():
        raise GatherError(f"Include path is not a file: {include_file}")

    if backups_dir:
        backups_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["docker", "run", "--rm"]
    cmd += volutils.rclone_docker_volume_flags(project)

    if backups_dir:
        cmd += ["-v", f"{str(backups_dir)}:/backups"]
    else:
        cmd += volutils.storage_docker_mount_flags(project, "backups", "/backups")

    cmd += ["-v", f"{str(include_file)}:/filters/backup-include.txt:ro"]

    if rclone_config_host.exists():
        cmd += ["-v", f"{str(rclone_config_host)}:/config/rclone:ro"]

    cmd += [RCLONE_IMAGE, "sync", "/data", "/backups", "--progress", "--include-from", "/filters/backup-include.txt"]

    run(cmd)
"""

Path("src/backups/gather.py").write_text(gather_content)

# 3. backup.py
backup_path = Path("runbook/backup.py")
b_text = backup_path.read_text()

old_b_text = '''    try:
        print("[stage:gather] Starting gather phase")
        gather_with_include_file(
            project=args.project,
            include_file=Path(args.include_file),
            backups_dir=backups_dir,
            rclone_config_host=Path(args.rclone_config_host),
        )
    except GatherError as err:
        raise SystemExit(f"[stage:gather] {err}") from err'''

new_b_text = '''    try:
        print("[stage:gather-sync] Starting gather phase: syncing volume files")
        gather_with_include_file(
            project=args.project,
            include_file=Path(args.include_file),
            backups_dir=backups_dir,
            rclone_config_host=Path(args.rclone_config_host),
        )
    except GatherError as err:
        raise SystemExit(f"[stage:gather-sync] {err}") from err

    if backups_dir:
        print("[stage:gather-snapshots] Creating DB snapshots locally")
        from src.backups.db_snapshot import create_db_snapshots, DbSnapshotError
        try:
            create_db_snapshots(backups_dir)
        except DbSnapshotError as err:
            print(f"[stage:gather-snapshots] WARNING: {err}")
    else:
        print(
            "Skipping host-side SQLite snapshot pass; backups are using a docker named volume."
        )'''

b_text = b_text.replace(old_b_text, new_b_text)
backup_path.write_text(b_text)

print("Done")
