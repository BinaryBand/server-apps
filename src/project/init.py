import subprocess

from src.utils.compose import compose_cmd
from src.utils.runtime import repo_root


if __name__ == "__main__":
    print("Initializing server apps...")

    root = repo_root()
    apply_perms = root / "scripts" / "apply-perms.sh"

    if not apply_perms.exists():
        raise SystemExit(f"Permissions script not found: {apply_perms}")

    print("Applying host permissions and rendering runtime templates via Ansible...")
    subprocess.run([str(apply_perms)], check=True)

    subprocess.run(compose_cmd("up", "-d"), check=True)

    print("Initialization complete.")
