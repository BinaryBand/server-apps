import subprocess


if __name__ == "__main__":
    print("Shutting down server apps...")

    subprocess.run(["docker", "compose", "down"], check=True)

    print("Shutdown complete.")
