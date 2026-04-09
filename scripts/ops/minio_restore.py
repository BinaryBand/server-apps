"""MinIO restore helper.

Usage:
    # Full restore
    python scripts/ops/minio_restore.py

    # Restore only one subtree
    python scripts/ops/minio_restore.py /media/podcasts/morbid

    # Restore everything under /media/podcasts except morbid and necronomipod
    python scripts/ops/minio_restore.py \
        --include /media/podcasts \
        --exclude /media/podcasts/morbid \
        --exclude /media/podcasts/necronomipod

Template:
    python scripts/ops/minio_restore.py /media/<category>/<item>
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore the full MinIO backup or a specific subpath."
    )
    parser.add_argument(
        "restore_path",
        nargs="?",
        help="Optional subpath to restore, e.g. /media/podcasts/morbid",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Include path prefix (repeatable), e.g. /media/podcasts",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude path prefix (repeatable), e.g. /media/podcasts/morbid",
    )
    return parser.parse_args()


def _normalized_relative_path(path: str) -> str:
    return PurePosixPath(path.strip().strip("/")).as_posix()


def rclone_restore_paths(restore_path: str | None) -> tuple[str, str]:
    if restore_path is None:
        return "pcloud:/Backups/Minio", "minio:"

    normalized = restore_path.strip().strip("/")
    if not normalized:
        return "pcloud:/Backups/Minio", "minio:"

    relative_path = _normalized_relative_path(normalized)
    return (
        f"pcloud:/Backups/Minio/{relative_path}",
        f"minio:{relative_path}",
    )


def rclone_filter_args(includes: list[str], excludes: list[str]) -> list[str]:
    args: list[str] = []

    normalized_excludes: list[str] = []
    for exclude_path in excludes:
        normalized = _normalized_relative_path(exclude_path)
        if normalized:
            normalized_excludes.append(normalized)

    normalized_includes: list[str] = []
    for include_path in includes:
        normalized = _normalized_relative_path(include_path)
        if normalized:
            normalized_includes.append(normalized)

    # Excludes must come first so they can override broader include prefixes.
    for normalized in normalized_excludes:
        args.extend(["--filter", f"- {normalized}/**"])

    for normalized in normalized_includes:
        args.extend(["--filter", f"+ {normalized}/**"])

    # When includes are provided, explicitly exclude everything else.
    if normalized_includes:
        args.extend(["--filter", "- **"])

    return args


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).parent.parent.parent.resolve()
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    from src.storage.compose import compose_cmd

    source_path, destination_path = rclone_restore_paths(args.restore_path)
    filter_args = rclone_filter_args(args.include, args.exclude)

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
            "sync",
            source_path,
            destination_path,
            *filter_args,
            "--progress",
        ),
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
