from src.utils.docker.compose import compose_cmd
from src.utils.docker.wrappers.rclone import cleanup_media_mount

import subprocess


def main():
    print("Shutting down server apps...")

    print("[stage:volumes] Cleaning up media mount")
    cleanup_media_mount()

    subprocess.run(compose_cmd("down"), check=True)
    print("Shutdown complete.")


if __name__ == "__main__":
    main()
