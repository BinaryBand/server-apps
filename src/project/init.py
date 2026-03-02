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

    env_values = dict(os.environ)
    if not env_values.get("MINIO_ROOT_USER") and env_values.get("S3_ACCESS_KEY"):
        env_values["MINIO_ROOT_USER"] = env_values["S3_ACCESS_KEY"]
    if not env_values.get("MINIO_ROOT_PASSWORD") and env_values.get("S3_SECRET_KEY"):
        env_values["MINIO_ROOT_PASSWORD"] = env_values["S3_SECRET_KEY"]
    if not env_values.get("S3_ACCESS_KEY") and env_values.get("MINIO_ROOT_USER"):
        env_values["S3_ACCESS_KEY"] = env_values["MINIO_ROOT_USER"]
    if not env_values.get("S3_SECRET_KEY") and env_values.get("MINIO_ROOT_PASSWORD"):
        env_values["S3_SECRET_KEY"] = env_values["MINIO_ROOT_PASSWORD"]

    # Simple ${VAR} substitution from environment
    for key, val in env_values.items():
        placeholder = f"${{{key}}}"
        if placeholder in text:
            text = text.replace(placeholder, val)

    dest_path.write_text(text, encoding="utf-8")
    print(f"Wrote rclone config to {dest_path}")


if __name__ == "__main__":
    print("Initializing server apps...")

    repo_root = Path(__file__).resolve().parents[2]
    template = repo_root / "configs/templates/rclone.template.conf"
    dest = repo_root / ".local" / "rclone" / "rclone.conf"

    render_rclone_template(template, dest)

    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose/base.yml",
            "-f",
            "compose/dev.yml",
            "up",
            "-d",
        ],
        check=True,
    )

    print("Initialization complete.")
