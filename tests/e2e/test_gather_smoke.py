from __future__ import annotations

from pathlib import Path
import sys
import shutil
import subprocess
import uuid

import pytest

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.toolbox.backups.gather import gather_stage
from src.toolbox.docker.volumes import logical_volume_names as _logical_volume_names
from src.toolbox.core.runtime import repo_root


DOCKER_PROBE_TIMEOUT_SECONDS = 30


def _stage_roots_from_include_file(include_file: Path) -> list[str]:
    roots: list[str] = []

    for raw_line in include_file.read_text(encoding="utf8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("/")
        if len(parts) < 2:
            continue

        root = "/".join(parts[:2]).rstrip("/")
        if root and root not in roots:
            roots.append(root)

    return roots


@pytest.fixture
def gather_env(repo_root, docker_available):
    if not docker_available:
        pytest.skip("docker is required for gather smoke tests")

    probe = subprocess.run([
        "docker",
        "info",
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode != 0:
        pytest.skip("docker daemon is not available")

    include_file = repo_root / "configs" / "backup-include.txt"
    stage_roots = _stage_roots_from_include_file(include_file)
    logical_volume_names = _logical_volume_names()
    source_volumes: dict[str, str] = {
        logical_name: f"smoke-gather-{uuid.uuid4().hex[:8]}-{logical_name}"
        for logical_name in logical_volume_names
    }

    for volume_name in source_volumes.values():
        subprocess.run(
            ["docker", "volume", "create", volume_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    for logical_name, volume_name in source_volumes.items():
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{volume_name}:/target",
                "alpine:3.20",
                "sh",
                "-lc",
                (
                    "set -eu && "
                    "mkdir -p /target/data && "
                    f"printf '%s\n' smoke > /target/data/{logical_name}.txt"
                ),
            ],
            check=True,
        )

    yield {
        "include_file": include_file,
        "stage_roots": stage_roots,
        "logical_volume_names": logical_volume_names,
        "source_volumes": source_volumes,
    }

    for volume_name in source_volumes.values():
        subprocess.run(
            ["docker", "volume", "rm", "-f", volume_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _assert_container_path_has_content(docker_args: list[str], container_path: str) -> None:
    try:
        probe = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                *docker_args,
                "alpine:3.20",
                "sh",
                "-lc",
                (
                    f"test -d '{container_path}' && "
                    f"find '{container_path}' -mindepth 1 -print -quit | grep -q ."
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=DOCKER_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as err:
        pytest.fail(f"Timed out while probing {container_path}: {err}")

    assert probe.returncode == 0, (
        f"Expected populated gather source at {container_path}.\n"
        f"stdout:\n{probe.stdout}\n"
        f"stderr:\n{probe.stderr}"
    )


def test_gather_mounts_populated_stage_roots(gather_env, monkeypatch) -> None:
    env = gather_env
    patched_flags: list[str] = []
    for logical_name in env["logical_volume_names"]:
        source_volume = env["source_volumes"][logical_name]
        patched_flags += ["-v", f"{source_volume}:/data/volumes/{logical_name}:ro"]

    def fake_rclone_sync(
        source: str,
        destination: str,
        *,
        docker_args: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        assert source == "/data"
        assert destination == "/backups"
        assert docker_args is not None
        assert extra_args == ["--include-from", "/filters/backup-include.txt"]

        try:
            include_probe = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    *(docker_args or []),
                    "alpine:3.20",
                    "sh",
                    "-lc",
                    "test -f /filters/backup-include.txt",
                ],
                check=False,
                timeout=DOCKER_PROBE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as err:
            pytest.fail(f"Timed out while probing mounted include file: {err}")

        assert include_probe.returncode == 0

        for root in env["stage_roots"]:
            _assert_container_path_has_content(docker_args or [], f"/data/{root}")

    monkeypatch.setattr("src.toolbox.backups.gather.rclone_sync", fake_rclone_sync)
    monkeypatch.setattr(
        "src.toolbox.backups.gather.volatile.rclone_docker_volume_flags", lambda: patched_flags
    )

    gather_stage(env["include_file"]) 
