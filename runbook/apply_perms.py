import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

from runbook._bootstrap import repo_root


if __name__ == "__main__":
    root = repo_root()
    apply_perms_script = root / "scripts" / "apply-perms.sh"

    if not apply_perms_script.exists():
        raise SystemExit(f"Permissions script not found: {apply_perms_script}")

    subprocess.run([str(apply_perms_script), *sys.argv[1:]], check=True)
