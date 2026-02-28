import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv


def render_rclone_template(template_path: Path, dest_path: Path):
    load_dotenv()

    if not template_path.exists():
        print(f"Rclone template not found at {template_path}")
        return

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    text = template_path.read_text(encoding="utf-8")

    # Simple ${VAR} substitution from environment
    for key, val in os.environ.items():
        placeholder = f"${{{key}}}"
        if placeholder in text:
            text = text.replace(placeholder, val)

    dest_path.write_text(text, encoding="utf-8")
    print(f"Wrote rclone config to {dest_path}")


if __name__ == "__main__":
    print("Initializing server apps...")

    repo_root = Path(__file__).resolve().parents[1]
    template = repo_root / "configs/templates/rclone.template.conf"
    dest = repo_root / ".local" / "rclone" / "rclone.conf"

    render_rclone_template(template, dest)

    subprocess.run(["docker", "compose", "up", "-d"], check=True)

    print("Initialization complete.")
