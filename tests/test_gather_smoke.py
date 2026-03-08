from __future__ import annotations

from src.backups.gather import gather_with_include_file
from src.utils.runtime import PROJECT_NAME, repo_root

from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch
import shutil
import subprocess


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

        # Gather mounts top-level logical storage roots under /data/volumes/*.
        # Nested include patterns like `db-snapshots/**` are optional content
        # inside a staged root, not separate staging sources.
        root = "/".join(parts[:2]).rstrip("/")
        if root and root not in roots:
            roots.append(root)

    return roots


class GatherSmokeTest(TestCase):
    def setUp(self) -> None:
        if shutil.which("docker") is None:
            self.skipTest("docker is required for gather smoke tests")

        probe = subprocess.run(
            ["docker", "info"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode != 0:
            self.skipTest("docker daemon is not available")

        self.include_file = repo_root() / "configs" / "backup-include.txt"
        self.stage_roots = _stage_roots_from_include_file(self.include_file)

    def _assert_container_path_has_content(
        self, docker_args: list[str], container_path: str
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
            self.fail(f"Timed out while probing {container_path}: {err}")

        self.assertEqual(
            probe.returncode,
            0,
            msg=(
                f"Expected populated gather source at {container_path}.\n"
                f"stdout:\n{probe.stdout}\n"
                f"stderr:\n{probe.stderr}"
            ),
        )

    def test_gather_mounts_populated_stage_roots(self) -> None:
        def fake_rclone_sync(
            source: str,
            destination: str,
            *,
            docker_args: list[str] | None = None,
            extra_args: list[str] | None = None,
        ) -> None:
            self.assertEqual(source, "/data")
            self.assertEqual(destination, "/backups")
            self.assertIsNotNone(docker_args)
            self.assertEqual(
                extra_args,
                ["--include-from", "/filters/backup-include.txt"],
            )

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
                self.fail(f"Timed out while probing mounted include file: {err}")

            self.assertEqual(include_probe.returncode, 0)

            for root in self.stage_roots:
                self._assert_container_path_has_content(
                    docker_args or [], f"/data/{root}"
                )

        with patch("src.backups.gather.rclone_sync", side_effect=fake_rclone_sync):
            gather_with_include_file(PROJECT_NAME, self.include_file)


if __name__ == "__main__":
    main()
