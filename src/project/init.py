import subprocess

from src.utils.compose import compose_cmd, ensure_external_volumes
from src.utils.runtime import repo_root


if __name__ == "__main__":
    print("Initializing server apps...")

    root = repo_root()
    apply_perms = root / "scripts" / "apply-perms.sh"

    if not apply_perms.exists():
        raise SystemExit(f"Permissions script not found: {apply_perms}")

    print("Preparing runtime directories and templates via Ansible (non-privileged)...")
    subprocess.run(["bash", str(apply_perms), "--runtime"], check=True)

    print("Ensuring required external Docker volumes exist...")
    ensure_external_volumes()

    subprocess.run(compose_cmd("up", "-d"), check=True)

    print("Initialization complete.")
