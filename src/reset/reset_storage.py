from dotenv import find_dotenv
from pathlib import Path
import sys
import os
import subprocess
import argparse


_ROOT = Path(find_dotenv()).parent
sys.path.insert(0, str(_ROOT))


def get_project_name():
    # Respect PROJECT_NAME if set, otherwise use directory name
    return os.environ.get("PROJECT_NAME") or Path(_ROOT).name


def list_compose_volumes(project: str):
    # Try to use docker volume ls with compose label
    try:
        cmd = [
            "docker",
            "volume",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.Name}}",
        ]
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        vols = [line for line in proc.stdout.splitlines() if line.strip()]
        if vols:
            return vols
    except FileNotFoundError:
        print("docker CLI not found.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        # fallthrough to name prefix method
        pass

    # Fallback: list all volumes and filter by name prefix
    try:
        cmd = ["docker", "volume", "ls", "--format", "{{.Name}}"]
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        prefix = f"{project}_"
        vols = [line for line in proc.stdout.splitlines() if line.startswith(prefix)]
        return vols
    except subprocess.CalledProcessError as exc:
        print("Failed to list docker volumes:", exc)
        sys.exit(1)


def remove_volumes(volumes):
    removed = []
    failed = []
    for v in volumes:
        try:
            subprocess.run(["docker", "volume", "rm", "-f", v], check=True)
            removed.append(v)
        except subprocess.CalledProcessError:
            failed.append(v)
    return removed, failed


def main():
    parser = argparse.ArgumentParser(
        description="Remove all Docker volumes or run conservative compose down"
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Skip prompt")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List volumes only / show compose command",
    )
    parser.add_argument(
        "--compose-down",
        action="store_true",
        help="Run `docker compose down --volumes --rmi local --remove-orphans` for this project",
    )
    args = parser.parse_args()

    project = get_project_name()
    print(f"Project name: {project}")

    # If user requested conservative compose-down, run that command instead
    if args.compose_down:
        cmd = [
            "docker",
            "compose",
            "down",
            "--volumes",
            "--rmi",
            "local",
            "--remove-orphans",
        ]
        print("Compose down command:", " ".join(cmd))
        if args.dry_run:
            print("Dry run; not executing compose down.")
            return
        if not args.yes:
            ok = (
                input("Run compose down for this project? [y/N]: ").strip().lower()
                == "y"
            )
            if not ok:
                print("Aborted by user.")
                return
        try:
            subprocess.run(cmd, check=True)
            print("docker compose down completed.")
        except subprocess.CalledProcessError as exc:
            print("docker compose down failed:", exc)
        return

    vols = list_compose_volumes(project)
    if not vols:
        print("No docker volumes found for this project.")
        return

    print("Found docker volumes:")
    for v in vols:
        print(" -", v)

    if args.dry_run:
        print("Dry run requested; no volumes will be removed.")
        return

    if not args.yes:
        ok = input("Remove these volumes? [y/N]: ").strip().lower() == "y"
        if not ok:
            print("Aborted by user.")
            return

    removed, failed = remove_volumes(vols)
    print(f"Removed: {len(removed)}; Failed: {len(failed)}")
    if failed:
        print("Failed to remove:")
        for v in failed:
            print(" -", v)


if __name__ == "__main__":
    main()
