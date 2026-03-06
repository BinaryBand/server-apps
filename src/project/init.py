import subprocess
import os
import re
from pathlib import Path

from src.utils.secrets import read_all_secrets, read_secret_alias


def ensure_logs_permissions(repo_root: Path) -> None:
    logs_dir = repo_root / ".local" / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    try:
        os.chmod(logs_dir, 0o777)
    except PermissionError:
        print(f"Warning: cannot chmod {logs_dir}; run with sudo if needed")

    for log_file in logs_dir.glob("*.log"):
        try:
            os.chmod(log_file, 0o666)
        except OSError:
            pass

    try:
        access_acl = subprocess.run(
            ["setfacl", "-m", "u::rwx,g::rwx,o::rwx", str(logs_dir)],
            check=False,
            capture_output=True,
            text=True,
        )
        default_acl = subprocess.run(
            ["setfacl", "-d", "-m", "u::rwx,g::rwx,o::rwx", str(logs_dir)],
            check=False,
            capture_output=True,
            text=True,
        )
        if access_acl.returncode != 0 or default_acl.returncode != 0:
            print("Warning: setfacl could not be applied for .local/logs")
    except FileNotFoundError:
        print("Warning: setfacl not installed; new log files may not be world-writable")


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
    ensure_logs_permissions(repo_root)

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
