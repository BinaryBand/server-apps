import subprocess


if __name__ == "__main__":
    print("Initializing server apps...")

    subprocess.run(["docker", "compose", "up", "-d"], check=True)

    print("Initialization complete.")
