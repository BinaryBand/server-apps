from __future__ import annotations

import subprocess
from typing import Iterable


def create_volumes(names: Iterable[str]) -> None:
    for n in names:
        subprocess.run(["docker", "volume", "create", n], check=True)


def remove_volumes(names: Iterable[str]) -> None:
    for n in names:
        subprocess.run(["docker", "volume", "rm", "-f", n], check=False)
