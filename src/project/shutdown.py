import subprocess

from src.utils.compose import compose_cmd


if __name__ == "__main__":
    print("Shutting down server apps...")

    subprocess.run(compose_cmd("down"), check=True)

    print("Shutdown complete.")
