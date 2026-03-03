import argparse
import sqlite3
from pathlib import Path


def snapshot_sqlite(source_path: Path, output_path: Path) -> None:
    src = source_path.resolve()
    dst = output_path.resolve()

    if not src.exists() or not src.is_file():
        raise SystemExit(f"Source SQLite file not found: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    src_uri = f"file:{src.as_posix()}?mode=ro"
    with sqlite3.connect(src_uri, uri=True) as source_conn:
        source_conn.execute("PRAGMA busy_timeout = 15000")
        with sqlite3.connect(str(dst)) as dest_conn:
            source_conn.backup(dest_conn)
            dest_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a hot SQLite snapshot from source file to destination file"
    )
    parser.add_argument("source_path", help="Path to source SQLite file")
    parser.add_argument("output_path", help="Path to destination snapshot file")
    args = parser.parse_args()

    snapshot_sqlite(Path(args.source_path), Path(args.output_path))
    print(f"Snapshot written to: {Path(args.output_path).resolve()}")


if __name__ == "__main__":
    main()
