from pathlib import Path
import subprocess


RCLONE_IMAGE = "rclone/rclone:latest"


def run(cmd):
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def gather_with_include_file(
    project: str, include_file: Path, backups_dir: Path, rclone_config_host: Path
):
    backups_dir = backups_dir.resolve()
    include_file = include_file.resolve()
    rclone_config_host = rclone_config_host.resolve()

    if not include_file.exists():
        raise SystemExit(f"Include file not found: {include_file}")
    if not include_file.is_file():
        raise SystemExit(f"Include path is not a file: {include_file}")

    backups_dir.mkdir(parents=True, exist_ok=True)

    jellyfin_config_vol = f"{project}_jellyfin_config"
    jellyfin_data_vol = f"{project}_jellyfin_data"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{jellyfin_config_vol}:/data/volumes/jellyfin_config:ro",
        "-v",
        f"{jellyfin_data_vol}:/data/volumes/jellyfin_data:ro",
        "-v",
        f"{str(backups_dir)}:/backups",
        "-v",
        f"{str(include_file)}:/filters/filter.txt:ro",
    ]

    if rclone_config_host.exists():
        cmd += ["-v", f"{str(rclone_config_host)}:/config/rclone:ro"]

    cmd += [
        RCLONE_IMAGE,
        "sync",
        "/data",
        "/backups",
        "--include-from",
        "/filters/filter.txt",
    ]

    run(cmd)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Gather selected paths from docker volumes to local backups via rclone"
    )
    parser.add_argument("--project", required=True, help="Compose project name")
    parser.add_argument("--include-file", required=True, help="Path to include file")
    parser.add_argument("--backups-dir", required=True, help="Host backups directory")
    parser.add_argument("--rclone-config-host", required=True, help="Host config")
    args = parser.parse_args()

    gather_with_include_file(
        project=args.project,
        include_file=Path(args.include_file),
        backups_dir=Path(args.backups_dir),
        rclone_config_host=Path(args.rclone_config_host),
    )


if __name__ == "__main__":
    main()
