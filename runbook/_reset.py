from src.utils.docker.compose import compose_cmd
from src.utils.permissions import run_permissions_playbook
from src.utils.runtime import (
    PROJECT_NAME,
    backups_root,
    logs_root,
    media_root,
    repo_root,
    restic_repo_root,
)
from src.utils.docker.volumes import list_project_volumes

from argparse import ArgumentParser, Namespace
from pathlib import Path
import subprocess
import shutil


REPO_ROOT: Path = repo_root()
LOCAL_ROOT: Path = REPO_ROOT / "runtime"


def remove_project_volumes(project: str, *, dry_run: bool = False) -> tuple[int, int]:
    volumes = list_project_volumes(project)
    if not volumes:
        print("No project volumes found.")
        return (0, 0)

    removed = 0
    failed = 0
    for volume in volumes:
        try:
            subprocess.run(["docker", "volume", "rm", "-f", volume], check=True)
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


def normalize_reset_permissions(*, dry_run: bool = False) -> None:
    if dry_run:
        print("Running: ansible-playbook apply-permissions.yml --check (reset mode)")
    run_permissions_playbook(mode="reset", dry_run=dry_run)


def main() -> None:
    parser = ArgumentParser(description="Reset project storage and runtime state")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument("--keep-restic", action="store_true")
    parser.add_argument("--keep-media", action="store_true")
    parser.add_argument("--skip-compose-down", action="store_true")
    args: Namespace = parser.parse_args()

    targets: list[Path] = [logs_root()]
    configured_backups_root = backups_root()
    if configured_backups_root is not None:
        targets.append(configured_backups_root)
    configured_restic_root = restic_repo_root()
    if not args.keep_restic and configured_restic_root is not None:
        targets.append(configured_restic_root)
    if not args.keep_media:
        targets.append(media_root())

    print(f"Project: {PROJECT_NAME}")
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
        subprocess.run(
            compose_cmd("down", "--volumes", "--remove-orphans"), check=False
        )

    removed, failed = remove_project_volumes(PROJECT_NAME, dry_run=args.dry_run)
    print(f"Project volumes removed: {removed}, failed: {failed}")

    print("Normalizing local reset-path permissions via Ansible...")
    normalize_reset_permissions(dry_run=args.dry_run)

    for target in targets:
        remove_local_path(target, dry_run=args.dry_run)

    if not args.dry_run:
        if args.keep_media:
            media_root().mkdir(parents=True, exist_ok=True)
        print("Clean slate reset complete.")
    else:
        print("Dry run complete.")


if __name__ == "__main__":
    main()
