from __future__ import annotations

from pathlib import Path
import sys
import subprocess
import uuid

import pytest

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backup.gather import gather_stage
from src.configuration.backup_config import BackupConfig
from src.storage.volumes import logical_volume_names as _logical_volume_names


DOCKER_PROBE_TIMEOUT_SECONDS = 30


def _stage_roots_from_include_patterns(patterns: list[str]) -> list[str]:
    """Extract the top-two path components from include patterns.

    e.g. "volumes/jellyfin_config/**" → "volumes/jellyfin_config"
    """
    roots: list[str] = []
    for pattern in patterns:
        parts = pattern.split("/")
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

    probe = subprocess.run(
        ["docker", "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode != 0:
        pytest.skip("docker daemon is not available")

    config = BackupConfig.from_toml(repo_root / "configs" / "backup.toml")
    stage_roots = _stage_roots_from_include_patterns(config.batch.include)
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
        "config": config,
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


def _assert_container_path_has_content(
    docker_args: list[str], container_path: str
) -> None:
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
        # All filters use --filter flags (no --include-from or bare --include/--exclude)
        assert extra_args is not None
        filter_flags = [a for a in extra_args if a == "--filter"]
        assert len(filter_flags) > 0, "Expected at least one --filter flag"
        assert "--include-from" not in extra_args
        assert "--include" not in extra_args

        for root in env["stage_roots"]:
            _assert_container_path_has_content(docker_args or [], f"/data/{root}")

    monkeypatch.setattr(
        "src.toolbox.docker.wrappers.rclone.rclone_sync", fake_rclone_sync
    )
    monkeypatch.setattr(
        "src.storage.volumes.rclone_docker_volume_flags",
        lambda: patched_flags,
    )

    config: BackupConfig = env["config"]
    gather_stage(config.batch.include, config.batch.exclude)
