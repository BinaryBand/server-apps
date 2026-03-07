import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from src.utils.compose import compose_cmd
from src.utils.secrets import load_env
from src.utils.runtime import (
    backups_root,
    local_root,
    logs_root,
    media_root,
    project_name,
    repo_root,
    restic_repo_root,
)


REPO_ROOT = repo_root()
LOCAL_ROOT = local_root()


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


def normalize_reset_permissions(*, dry_run: bool = False) -> None:
    apply_perms_script = REPO_ROOT / "scripts" / "apply-perms.sh"
    if not apply_perms_script.exists():
        raise SystemExit(f"Permissions script not found: {apply_perms_script}")
    run_command(["bash", str(apply_perms_script), "--reset"], dry_run=dry_run)


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
        help="Keep host restic repository override",
    )
    parser.add_argument(
        "--keep-media",
        action="store_true",
        help="Keep configured media mount directory contents",
    )
    parser.add_argument(
        "--skip-compose-down",
        action="store_true",
        help="Do not run docker compose down --volumes --remove-orphans",
    )
    args = parser.parse_args()

    project = project_name()

    targets: list[Path] = [
        logs_root(),
    ]
    configured_backups_root = backups_root()
    if configured_backups_root is not None:
        targets.append(configured_backups_root)
    configured_restic_root = restic_repo_root()
    if not args.keep_restic and configured_restic_root is not None:
        targets.append(configured_restic_root)
    if not args.keep_media:
        targets.append(media_root())

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
            compose_cmd("down", "--volumes", "--remove-orphans"),
            dry_run=args.dry_run,
            check=False,
        )

    removed, failed = remove_project_volumes(project, dry_run=args.dry_run)
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
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted.")
        sys.exit(130)
