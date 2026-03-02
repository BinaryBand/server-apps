import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from src.utils.secrets import load_env, read_secret


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ROOT = REPO_ROOT / ".local"


def get_project_name() -> str:
    return read_secret("PROJECT_NAME") or REPO_ROOT.name


def run_command(cmd: list[str], *, dry_run: bool = False, check: bool = True) -> int:
    print("Running:", " ".join(cmd))
    if dry_run:
        return 0
    completed = subprocess.run(cmd, check=False)
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)
    return completed.returncode


def list_project_volumes(project: str) -> list[str]:
    cmd = [
        "docker",
        "volume",
        "ls",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--format",
        "{{.Name}}",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode == 0:
        volumes = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if volumes:
            return volumes

    fallback = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if fallback.returncode != 0:
        return []
    prefix = f"{project}_"
    return [
        line.strip() for line in fallback.stdout.splitlines() if line.startswith(prefix)
    ]


def remove_project_volumes(project: str, *, dry_run: bool = False) -> tuple[int, int]:
    volumes = list_project_volumes(project)
    if not volumes:
        print("No project volumes found.")
        return (0, 0)

    removed = 0
    failed = 0
    for volume in volumes:
        try:
            run_command(["docker", "volume", "rm", "-f", volume], dry_run=dry_run)
            removed += 1
        except subprocess.CalledProcessError:
            failed += 1
            print(f"Failed to remove volume: {volume}")
    return (removed, failed)


def remove_local_path(path: Path, *, dry_run: bool = False) -> None:
    if not path.exists():
        return
    print(f"Removing: {path}")
    if dry_run:
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def main() -> None:
    load_env(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Reset project runtime storage to a clean slate"
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument(
        "--keep-restic",
        action="store_true",
        help="Keep .local/restic repository",
    )
    parser.add_argument(
        "--keep-media",
        action="store_true",
        help="Keep .local/media mount directory contents",
    )
    parser.add_argument(
        "--skip-compose-down",
        action="store_true",
        help="Do not run docker compose down --volumes --remove-orphans",
    )
    args = parser.parse_args()

    project = get_project_name()

    targets: list[Path] = [
        LOCAL_ROOT / "backups",
        LOCAL_ROOT / "logs",
        LOCAL_ROOT / "rclone" / "rclone.conf",
    ]
    if not args.keep_restic:
        targets.append(LOCAL_ROOT / "restic")
    if not args.keep_media:
        targets.append(LOCAL_ROOT / "media")

    print(f"Project: {project}")
    print("This will remove Docker runtime data and local state:")
    print(" - docker compose down --volumes --remove-orphans")
    print(" - project Docker volumes")
    for target in targets:
        print(f" - {target}")

    if not args.yes:
        proceed = input("Proceed with clean-slate reset? [y/N]: ").strip().lower()
        if proceed != "y":
            print("Aborted.")
            return

    if not args.skip_compose_down:
        run_command(
            ["docker", "compose", "down", "--volumes", "--remove-orphans"],
            dry_run=args.dry_run,
            check=False,
        )

    removed, failed = remove_project_volumes(project, dry_run=args.dry_run)
    print(f"Project volumes removed: {removed}, failed: {failed}")

    for target in targets:
        remove_local_path(target, dry_run=args.dry_run)

    if not args.dry_run:
        (LOCAL_ROOT / "rclone").mkdir(parents=True, exist_ok=True)
        if args.keep_media:
            (LOCAL_ROOT / "media").mkdir(parents=True, exist_ok=True)
        print("Clean slate reset complete.")
    else:
        print("Dry run complete.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted.")
        sys.exit(130)
