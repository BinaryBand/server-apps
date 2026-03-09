from __future__ import annotations

from src.utils.docker.post_start.errors import RuntimePostStartError

import subprocess


def restart_jellyfin() -> None:
    try:
        subprocess.run(["docker", "restart", "jellyfin"], check=True)
    except subprocess.CalledProcessError as err:
        raise RuntimePostStartError("failed to restart jellyfin") from err
