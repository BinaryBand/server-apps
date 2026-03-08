from src.utils.docker.compose import compose_cmd
from src.utils.permissions import run_permissions_playbook
from src.utils.runtime import PROJECT_NAME
import subprocess
import os


def main():
    print("Initializing apps...")
    # Ensure the playbook sees the canonical project name used by the runtime
    os.environ.setdefault("PROJECT_NAME", PROJECT_NAME)
    run_permissions_playbook(mode="runtime")
    subprocess.run(compose_cmd("up", "-d"), check=True)
    print("Initialization complete.")


if __name__ == "__main__":
    main()
