from pathlib import Path
import subprocess

from src.backups.db_snapshot import snapshot_sqlite
from src.utils.secrets import read_secret
from src.utils import volumes as volutils


RCLONE_IMAGE: str = (
    read_secret("RCLONE_IMAGE")
    or f"rclone/rclone:{read_secret('RCLONE_VERSION', 'latest')}"
)
SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}


class GatherError(RuntimeError):
    """Raised when gather operations fail."""



def run(cmd):
    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        raise GatherError(
            f"Gather command failed with exit code {err.returncode}: {' '.join(cmd)}"
        ) from err


def _is_sqlite_candidate(file_path: Path) -> bool:
    if "db-snapshots" in file_path.parts:
        return False
    if file_path.name.lower().endswith(".snapshot.db"):
        return False
    return file_path.suffix.lower() in SQLITE_EXTENSIONS


def _create_db_snapshots(backups_dir: Path) -> None:
    volume_dirs = volutils.gathered_volume_dirs(backups_dir)
    if not volume_dirs:
        print(f"Skipping db snapshot pass; no volumes found under: {backups_dir / 'volumes'}")
        return

    for volume_dir in volume_dirs:
        _create_db_snapshots_for_volume(volume_dir)


def _create_db_snapshots_for_volume(volume_dir: Path) -> None:
    # Prefer the conventional 'data' subdirectory, but fall back to scanning
    # the entire volume directory in case files use a different layout.
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
        print(
            f"SQLite snapshot pass completed with {len(failures)} failure(s); continuing with gathered files."
        )


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
    if backups_dir:
        _create_db_snapshots(backups_dir)
    else:
        print(
            "Skipping host-side SQLite snapshot pass; backups are using a docker named volume."
        )


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
