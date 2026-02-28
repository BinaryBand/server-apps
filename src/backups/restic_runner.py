import os
import subprocess


PROFILE = "on-demand"


def run_restic_command(cmd_args):
    docker_compose = os.environ.get("DOCKER_COMPOSE_CMD", "docker-compose")
    cmd = [
        docker_compose,
        "--profile",
        PROFILE,
        "run",
        "--rm",
        "--no-deps",
        "restic",
    ] + cmd_args
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_backup(paths=None, restic_args=None):
    backup_paths = paths or ["/backups"]
    extra_args = restic_args or []

    try:
        run_restic_command(["snapshots"])
    except subprocess.CalledProcessError:
        print("Restic repository is not initialized yet. Running 'restic init'.")
        run_restic_command(["init"])

    run_restic_command(["backup", *backup_paths, *extra_args])
