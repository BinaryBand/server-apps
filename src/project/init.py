import subprocess
import os
import re
from pathlib import Path

from src.utils.secrets import read_all_secrets, read_secret_alias


def render_rclone_template(template_path: Path, dest_path: Path):
    if not template_path.exists():
        print(f"Rclone template not found at {template_path}")
        return

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    text = template_path.read_text(encoding="utf-8")

    env_values = read_all_secrets()

    minio_root_user = read_secret_alias("MINIO_ROOT_USER", "S3_ACCESS_KEY")
    minio_root_password = read_secret_alias("MINIO_ROOT_PASSWORD", "S3_SECRET_KEY")

    if minio_root_user:
        env_values["MINIO_ROOT_USER"] = minio_root_user
        env_values["S3_ACCESS_KEY"] = minio_root_user
    if minio_root_password:
        env_values["MINIO_ROOT_PASSWORD"] = minio_root_password
        env_values["S3_SECRET_KEY"] = minio_root_password

    placeholder_pattern = re.compile(r"\$\{([A-Z0-9_]+)\}")
    placeholders = sorted(set(placeholder_pattern.findall(text)))
    missing = [name for name in placeholders if not env_values.get(name)]
    if missing:
        raise SystemExit("Missing required environment variable: " + ", ".join(missing))

    for name in placeholders:
        text = text.replace(f"${{{name}}}", env_values[name])

    dest_path.write_text(text, encoding="utf-8")
    try:
        os.chmod(dest_path, 0o600)
    except OSError:
        pass
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
