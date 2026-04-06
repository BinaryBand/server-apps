#!/usr/bin/env python3
"""Interactive helper to obtain a pCloud token via rclone and install rclone.conf.

Usage examples:
  # interactive attempt (will try local rclone, then docker):
  python runbook/authorize_rclone.py --install-volume

  # headless: print URL and accept pasted token JSON
  python runbook/authorize_rclone.py --headless --install-volume

This script is conservative: it will ask before writing secrets to `.env`.
It prefers installing a `rclone.conf` into the Docker volume `rclone_config`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import os
import textwrap


def _parse_token_from_text(text: str) -> dict | None:
    """Parse token JSON from either raw JSON or a chunk of text that contains
    a JSON object. Returns the dict on success or None.
    """
    if not text:
        return None

    # Fast path: try to parse the whole text as JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    snippet = _find_json_snippet(text)
    if snippet is None:
        return None
    try:
        return json.loads(snippet)
    except Exception:
        return None


def _find_json_snippet(text: str) -> str | None:
    """Return the first {...} balanced substring found in `text`, or None."""
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _attempt_local_rclone(headless: bool) -> dict | None:
    if shutil.which("rclone") is None:
        return None
    cmd = ["rclone", "authorize", "pcloud"]
    if headless:
        cmd.append("--auth-no-open-browser")
    return _run_and_parse(cmd)


def _attempt_docker_rclone(headless: bool, rclone_version: str | None) -> dict | None:
    if shutil.which("docker") is None:
        return None
    image = f"rclone/rclone:{rclone_version or 'latest'}"
    cmd = ["docker", "run", "--rm", image, "authorize", "pcloud"]
    if headless:
        cmd.append("--auth-no-open-browser")
    return _run_and_parse(cmd)


def _run_and_parse(cmd: list[str]) -> dict | None:
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return _parse_token_from_text(proc.stdout or proc.stderr)


def _write_rclone_conf(remote_name: str, token: dict, out_path: Path) -> None:
    token_json = json.dumps(token, separators=(",", ":"))
    content = textwrap.dedent(f"""
    [{remote_name}]
    type = pcloud
    token = {token_json}
    """)
    out_path.write_text(content)


def install_rclone_conf_to_volume(local_conf: Path, volume: str = "rclone_config") -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("docker is required to install rclone.conf into a Docker volume")
    parent = str(local_conf.resolve().parent)
    name = local_conf.name
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{volume}:/config/rclone",
        "-v",
        f"{parent}:/staging",
        "alpine:3.20",
        "sh",
        "-c",
        f"cp /staging/{name} /config/rclone/rclone.conf && chmod 600 /config/rclone/rclone.conf",
    ]
    subprocess.run(cmd, check=True)


def _update_env_file(token: dict, env_path: Path = Path(".env")) -> None:
    access = token.get("access_token")
    expiry = token.get("expiry") or ""
    token_type = token.get("token_type") or ""
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    def set_var(lines, key, value):
        for i, l in enumerate(lines):
            if l.startswith(key + "="):
                lines[i] = f"{key}={value}"
                return lines
        lines.append(f"{key}={value}")
        return lines

    lines = set_var(lines, "PCLOUD_ACCESS_TOKEN", access or "")
    lines = set_var(lines, "PCLOUD_TOKEN_TYPE", token_type)
    lines = set_var(lines, "PCLOUD_EXPIRY", expiry)
    env_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description="Authorize rclone for pCloud and install rclone.conf")
    p.add_argument("--headless", action="store_true", help="Do not attempt to open a browser; print URL and accept pasted token JSON")
    p.add_argument("--install-volume", action="store_true", help="Install generated rclone.conf into Docker volume 'rclone_config'")
    p.add_argument("--volume", default="rclone_config", help="Docker volume name to install rclone.conf into")
    p.add_argument("--export-env", action="store_true", help="Write PCLOUD_ACCESS_TOKEN and PCLOUD_EXPIRY into local .env (asks for confirmation)")
    p.add_argument("--rclone-version", default=None, help="rclone image version to use when running docker (default: image 'latest')")
    args = p.parse_args()

    def _existing_token_present() -> bool:
        existing = os.environ.get("PCLOUD_ACCESS_TOKEN")
        if existing:
            return True
        return _token_in_envfile()


    def _token_in_envfile() -> bool:
        envp = Path(".env")
        if not envp.exists():
            return False
        for line in envp.read_text().splitlines():
            if line.strip().startswith("PCLOUD_ACCESS_TOKEN="):
                _, val = line.split("=", 1)
                if val.strip():
                    return True
        return False

    def _obtain_token() -> dict | None:
        token = _attempt_local_rclone(args.headless)
        if token is not None:
            return token
        return _attempt_docker_rclone(args.headless, args.rclone_version)

    def _prompt_for_pasted_token() -> dict | None:
        print("Could not automatically obtain token.\n")
        print("Please run the following on a machine with a browser, then paste the JSON token here:")
        print("")
        print("  docker run --rm -it rclone/rclone:latest authorize pcloud")
        print("")
        print("Or (headless):")
        print("  docker run --rm rclone/rclone:latest authorize pcloud --auth-no-open-browser")
        print("")
        print("After completing the flow, paste the full JSON token and then an empty line.")
        print("")
        pasted = []
        try:
            while True:
                line = input()
                if not line.strip():
                    break
                pasted.append(line)
        except EOFError:
            pass
        return _parse_token_from_text("\n".join(pasted))

    def _install_and_maybe_export(token: dict) -> int:
        remote_name = os.environ.get("RCLONE_REMOTE", "pcloud")
        with tempfile.TemporaryDirectory() as td:
            tdpath = Path(td)
            conf_path = tdpath / "rclone.conf"
            _write_rclone_conf(remote_name, token, conf_path)

            if args.install_volume:
                rc = _try_install_volume(conf_path, args.volume)
                if rc != 0:
                    return rc

            if args.export_env:
                rc = _try_export_env(token)
                if rc != 0:
                    return rc

        return 0

    if _existing_token_present():
        print("PCLOUD_ACCESS_TOKEN already present in environment or .env; nothing to do.")
        return 0

    token = _obtain_token()
    if token is None:
        token = _prompt_for_pasted_token()
        if token is None:
            print("No valid token JSON found. Exiting.")
            return 2

    return _install_and_maybe_export(token)


def _try_install_volume(conf_path: Path, volume: str) -> int:
    try:
        install_rclone_conf_to_volume(conf_path, volume=volume)
        print(f"Installed rclone.conf into Docker volume '{volume}'.")
        return 0
    except Exception as e:
        print(f"Failed to install into volume: {e}")
        return 3


def _try_export_env(token: dict) -> int:
    if not sys.stdin.isatty():
        print("Refusing to write secrets to .env in non-interactive context.")
        return 4
    confirm = input("Write PCLOUD_ACCESS_TOKEN into .env in this directory? (y/N): ").strip().lower()
    if confirm == "y":
        _update_env_file(token)
        print("Wrote PCLOUD_ACCESS_TOKEN and PCLOUD_EXPIRY into .env (please ensure .env is not committed).")
        return 0
    print("Skipping .env write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
