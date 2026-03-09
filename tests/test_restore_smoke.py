from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backups.restore import restore_snapshot
from src.utils.docker.volumes import logical_volume_names

from unittest import TestCase, main
from unittest.mock import patch
import shutil
import subprocess
import uuid


DOCKER_PROBE_TIMEOUT_SECONDS = 30
RESTORE_TARGET = "/backups/restore"
LOGICAL_VOLUME_NAMES = logical_volume_names()


class RestoreSmokeTest(TestCase):
    def setUp(self) -> None:
        if shutil.which("docker") is None:
            self.skipTest("docker is required for restore smoke tests")

        probe = subprocess.run(
            ["docker", "info"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode != 0:
            self.skipTest("docker daemon is not available")

        self.test_project = f"smoke-restore-{uuid.uuid4().hex[:8]}"
        self.backups_volume = f"{self.test_project}-backups-source"
        self.target_volumes = [
            f"{self.test_project}_{logical_name}"
            for logical_name in LOGICAL_VOLUME_NAMES
        ]

        self._create_volume(self.backups_volume)
        for volume_name in self.target_volumes:
            self._create_volume(volume_name)

        self._populate_backups_volume()

    def tearDown(self) -> None:
        for volume_name in [self.backups_volume, *self.target_volumes]:
            subprocess.run(
                ["docker", "volume", "rm", "-f", volume_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _create_volume(self, volume_name: str) -> None:
        subprocess.run(
            ["docker", "volume", "create", volume_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _populate_backups_volume(self) -> None:
        script_lines = ["set -eu"]
        for logical_name in LOGICAL_VOLUME_NAMES:
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
                f"{self.backups_volume}:/backups",
                "alpine:3.20",
                "sh",
                "-lc",
                " && ".join(script_lines),
            ],
            check=True,
        )

    def _assert_restore_source_and_target(
        self,
        docker_args: list[str],
        source_path: str,
        logical_name: str,
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
            self.fail(f"Timed out while probing restore path for {logical_name}: {err}")

        self.assertEqual(
            probe.returncode,
            0,
            msg=(
                f"Expected populated restore source for {logical_name} at {source_path}.\n"
                f"stdout:\n{probe.stdout}\n"
                f"stderr:\n{probe.stderr}"
            ),
        )

    def test_restore_applies_all_staged_logical_volumes(self) -> None:
        seen_logical_names: set[str] = set()

        def fake_rclone_sync(
            source: str,
            destination: str,
            *,
            docker_args: list[str] | None = None,
            extra_args: list[str] | None = None,
        ) -> None:
            self.assertEqual(destination, "/dest")
            self.assertIsNotNone(docker_args)
            self.assertIsNone(extra_args)
            self.assertTrue(source.startswith("/source-root/restore/volumes/"))

            logical_name = Path(source).parts[-1]
            seen_logical_names.add(logical_name)
            self._assert_restore_source_and_target(
                docker_args or [], source, logical_name
            )

        with (
            patch("src.backups.restore.pull_restic_from_cloud") as pull_repo,
            patch(
                "src.backups.restore.restic.run_restic_command"
            ) as run_restic_command,
            patch(
                "src.backups.restore.storage_mount_source",
                return_value=self.backups_volume,
            ),
            patch(
                "src.backups.restore.logical_volume_mount_source",
                side_effect=lambda project, logical: f"{self.test_project}_{logical}",
            ),
            patch("src.backups.restore.rclone_sync", side_effect=fake_rclone_sync),
        ):
            restore_snapshot(target=RESTORE_TARGET)

        pull_repo.assert_called_once_with()
        run_restic_command.assert_called_once_with(
            ["restore", "latest", "--target", RESTORE_TARGET]
        )
        self.assertEqual(seen_logical_names, set(LOGICAL_VOLUME_NAMES))


if __name__ == "__main__":
    main()
