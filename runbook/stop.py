from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.toolbox.docker.compose import compose_cmd
from src.toolbox.docker.wrappers.rclone import cleanup_media_mount
from src.managers.checkpoint import OperationCheckpoint
from src.toolbox.locking import RunbookLock
from src.toolbox.runtime import checkpoints_root, locks_root

import subprocess


def main():
    with RunbookLock("start-stop", locks_root()):
        checkpoint = OperationCheckpoint("stop", checkpoints_root(), resume=False)
        checkpoint.start(desired="Stopped")

        print("Shutting down server apps...")

        print("[stage:cleanup] Cleaning up media mount")
        cleanup_media_mount()
        checkpoint.mark_stage("cleanup", ok=True)

        print("[stage:shutdown] Stopping containers")
        subprocess.run(compose_cmd("down"), check=True)
        checkpoint.mark_stage("shutdown", ok=True)

        checkpoint.finish(observed="Stopped", ok=True)
        print("Shutdown complete.")


if __name__ == "__main__":
    main()
