import subprocess
from pathlib import Path


if __name__ == "__main__":
    print("Initializing server apps...")

    repo_root = Path(__file__).resolve().parents[2]
    apply_perms = repo_root / "scripts" / "apply-perms.sh"

    if not apply_perms.exists():
        raise SystemExit(f"Permissions script not found: {apply_perms}")

    # Render rclone config, prepare directories, and start compose stack via Ansible.
    subprocess.run(["bash", str(apply_perms), "--runtime"], check=True)

    print("Initialization complete.")
