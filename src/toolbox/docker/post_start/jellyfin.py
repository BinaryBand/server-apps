from __future__ import annotations

import subprocess


def restart_jellyfin() -> None:
    try:
        subprocess.run(["docker", "restart", "jellyfin"], check=True)
    except subprocess.CalledProcessError as err:
        raise RuntimeError("failed to restart jellyfin") from err
