from __future__ import annotations

import os
from subprocess import CompletedProcess
from unittest.mock import patch

from src.adapters.rclone.compress_stage import CompressStage
from src.configuration.backup_config import CompressSource


def _cp(cmd: list[str], returncode: int = 0, stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(cmd, returncode=returncode, stdout=stdout, stderr="")


def test_compress_stage_copies_config_and_runs_rclone(monkeypatch, tmp_path):
    # Prepare a simple compress source
    cs = CompressSource(
        name="notebook-archives",
        source="minio:notebook",
        patterns=["**/*"],
        destination="pcloud:Backups/Compressed/notebook",
    )

    # Capture subprocess.run calls (the cp docker run)
    run_calls = []

    def fake_run(cmd, *args, **kwargs):
        # record the command string
        run_calls.append(cmd)
        return _cp(cmd)

    # rclone_lsf should return a list of files that will be grouped by parent
    def fake_lsf(source, docker_args=None, extra_args=None):
        assert source == cs.source
        # return two files in two parent dirs
        return [".sync/readme.txt", ".resource/info.json"]

    # fake rclone_copy should create the downloaded directories under the
    # staging host path so that zip can operate on real files. We find the
    # staging host path from docker_args entries that end with ':/staging'.
    copy_calls = []

    def fake_copy(src, dest, docker_args=None, extra_args=None):
        copy_calls.append((src, dest, docker_args, extra_args))
        # find staging path
        staging = None
        if docker_args:
            for i, arg in enumerate(docker_args):
                if isinstance(arg, str) and arg.endswith(":/staging"):
                    staging = arg.split(":", 1)[0]
                    break
        # create expected download layout so zipping works
        if staging and src.startswith(cs.source + "/") and ":/staging" in ":/staging" and "/download/" in dest:
            # dest is like /staging/download/<parent>
            host_dest = dest.replace("/staging", staging)
            os.makedirs(host_dest, exist_ok=True)
            # create a dummy file
            with open(os.path.join(host_dest, "dummy.txt"), "w") as f:
                f.write("x")

    monkeypatch.setattr("subprocess.run", fake_run)
    # patch the names as used inside the compress_stage module
    monkeypatch.setattr(
        "src.adapters.rclone.compress_stage.rclone_lsf", fake_lsf
    )
    monkeypatch.setattr(
        "src.adapters.rclone.compress_stage.rclone_copy", fake_copy
    )

    stage = CompressStage(cs)
    # Run backup; should not raise
    stage.backup()

    # Assertions: subprocess.run was called to copy rclone.conf
    assert any(
        "rclone_config:/config/rclone" in c for c in (run_calls if isinstance(run_calls, list) else [run_calls])
    ), "rclone.conf copy not invoked"

    # rclone_lsf and rclone_copy should have been called
    assert len(copy_calls) >= 2
