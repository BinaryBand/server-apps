from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.docker.compose import compose_cmd
from src.utils.docker.wrappers.rclone import cleanup_media_mount

import subprocess


def main():
    print("Shutting down server apps...")

    print("[stage:cleanup] Cleaning up media mount")
    cleanup_media_mount()

    print("[stage:shutdown] Stopping containers")
    subprocess.run(compose_cmd("down"), check=True)

    print("Shutdown complete.")


if __name__ == "__main__":
    main()
