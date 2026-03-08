# cspell: words popenargs
import subprocess


def docker_run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    full_cmd = ["docker", "run", "--rm"] + list(cmd)
    return subprocess.run(full_cmd, check=check)
