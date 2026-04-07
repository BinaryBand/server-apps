from __future__ import annotations

from pathlib import Path
import sys
import subprocess
import uuid

import pytest

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.backup.restore import restore_snapshot
from src.storage.volumes import logical_volume_names as _logical_volume_names


DOCKER_PROBE_TIMEOUT_SECONDS = 30
RESTORE_TARGET = "/backups/restore"


@pytest.fixture
def restore_env(repo_root, docker_available):
    if not docker_available:
        pytest.skip("docker is required for restore smoke tests")

    probe = subprocess.run(
        [
            "docker",
            "info",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode != 0:
        pytest.skip("docker daemon is not available")

    logical_names = _logical_volume_names()
    test_project = f"smoke-restore-{uuid.uuid4().hex[:8]}"
    backups_volume = f"{test_project}-backups-source"
    target_volumes = [
        f"{test_project}_{logical_name}" for logical_name in logical_names
    ]

    subprocess.run(
        ["docker", "volume", "create", backups_volume],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for v in target_volumes:
        subprocess.run(
            ["docker", "volume", "create", v],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # populate backups volume
    script_lines = ["set -eu"]
    for logical_name in logical_names:
        script_lines.extend(
            [
                f"mkdir -p /backups/restore/volumes/{logical_name}",
                f"printf '%s\n' smoke > /backups/restore/volumes/{logical_name}/.smoke",
            ]
        )

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{backups_volume}:/backups",
            "alpine:3.20",
            "sh",
            "-lc",
            " && ".join(script_lines),
        ],
        check=True,
    )

    yield {
        "test_project": test_project,
        "backups_volume": backups_volume,
        "target_volumes": target_volumes,
        "logical_names": logical_names,
    }

    for volume_name in [backups_volume, *target_volumes]:
        subprocess.run(
            ["docker", "volume", "rm", "-f", volume_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _assert_restore_source_and_target(
    docker_args: list[str], source_path: str, logical_name: str
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
                    f"test -d '{source_path}' && "
                    f"find '{source_path}' -mindepth 1 -print -quit | grep -q . && "
                    "test -d /dest"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=DOCKER_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as err:
        pytest.fail(f"Timed out while probing restore path for {logical_name}: {err}")

    assert probe.returncode == 0, (
        f"Expected populated restore source for {logical_name} at {source_path}.\n"
        f"stdout:\n{probe.stdout}\n"
        f"stderr:\n{probe.stderr}"
    )


def test_restore_applies_all_staged_logical_volumes(restore_env, monkeypatch) -> None:
    env = restore_env
    seen_logical_names: set[str] = set()

    def fake_rclone_sync(
        source: str,
        destination: str,
        *,
        docker_args: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        assert destination == "/dest"
        assert docker_args is not None
        assert extra_args is None
        assert source.startswith("/source-root/restore/volumes/")

        logical_name = Path(source).parts[-1]
        seen_logical_names.add(logical_name)
        _assert_restore_source_and_target(docker_args or [], source, logical_name)

    monkeypatch.setattr(
        "src.backup.restore.pull_restic_from_cloud", lambda: None
    )
    monkeypatch.setattr(
        "src.backup.restic.run_restic_command", lambda args: None
    )
    monkeypatch.setattr(
        "src.storage.volumes.storage_mount_source",
        lambda *a, **k: env["backups_volume"],
    )
    monkeypatch.setattr(
        "src.storage.volumes.logical_volume_mount_source",
        lambda logical: f"{env['test_project']}_{logical}",
    )
    monkeypatch.setattr("src.toolbox.docker.wrappers.rclone.rclone_sync", fake_rclone_sync)

    restore_snapshot(target=RESTORE_TARGET)

    # simple assertions that the fake restic and pull were invoked by code paths; we used lambdas so just assert seen logical names
    assert seen_logical_names == set(env["logical_names"])
