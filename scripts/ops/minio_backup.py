import argparse
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Back up the full MinIO data set or a specific subpath."
    )
    parser.add_argument(
        "backup_path",
        nargs="?",
        help="Optional subpath to back up, e.g. /media/podcasts/morbid",
    )
    return parser.parse_args()


def rclone_backup_paths(backup_path: str | None) -> tuple[str, str]:
    if backup_path is None:
        return "minio:", "pcloud:/Backups/Minio"

    normalized = backup_path.strip().strip("/")
    if not normalized:
        return "minio:", "pcloud:/Backups/Minio"

    relative_path = PurePosixPath(normalized).as_posix()
    return (
        f"minio:{relative_path}",
        f"pcloud:/Backups/Minio/{relative_path}",
    )


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).parent.parent.parent.resolve()
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    from src.storage.compose import compose_cmd

    source_path, destination_path = rclone_backup_paths(args.backup_path)

    env = os.environ.copy()
    env.pop("DOCKER_HOST", None)
    env.pop("DOCKER_CONTEXT", None)
    env.pop("CONTAINER_HOST", None)

    subprocess.run(
        compose_cmd(
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "rclone",
            "rclone",
            "copy",
            source_path,
            destination_path,
            "--progress",
        ),
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()