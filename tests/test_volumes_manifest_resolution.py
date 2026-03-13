from __future__ import annotations

from src.toolbox.docker import volumes
from src.toolbox.core.runtime import repo_root

from unittest import TestCase, main
from unittest.mock import patch


class VolumesComposeResolutionTest(TestCase):
    def test_required_external_volume_names_excludes_bind_mounts(self) -> None:
        with patch(
            "src.toolbox.docker.volumes.external_alias_name_pairs",
            return_value={
                "cloud_jellyfin_config": "jellyfin_config",
                "backups_data": "backups_data",
                "rclone_config_data": "rclone_config",
            },
        ):
            names = volumes.required_external_volume_names()

        self.assertNotIn("minio_data", names)
        self.assertIn("jellyfin_config", names)
        self.assertIn("backups_data", names)

    def test_host_bind_path_uses_manifest_default_when_env_missing(self) -> None:
        with (
            patch(
                "src.toolbox.docker.volumes._logical_source",
                return_value=("bind", "ignored"),
            ),
            patch("src.toolbox.core.config.bind_mount_value", return_value=None),
        ):
            path = volumes.host_bind_path("minio_data")

        self.assertIsNotNone(path)
        self.assertEqual(path, (repo_root() / "minio").resolve())

    def test_host_bind_path_uses_env_path_when_set(self) -> None:
        with (
            patch(
                "src.toolbox.docker.volumes._logical_source",
                return_value=("bind", "ignored"),
            ),
            patch(
                "src.toolbox.core.config.bind_mount_value",
                return_value="./runtime/minio",
            ),
        ):
            path = volumes.host_bind_path("minio_data")

        self.assertEqual(path, (repo_root() / "runtime/minio").resolve())

    def test_storage_mount_source_uses_named_volume_suffixes(self) -> None:
        with (
            patch(
                "src.toolbox.docker.volumes._storage_source",
                return_value="rclone_config_data",
            ),
            patch(
                "src.toolbox.docker.volumes._resolve_volume_source",
                return_value="rclone_config",
            ),
        ):
            source = volumes.storage_mount_source("rclone_config")

        self.assertEqual(source, "rclone_config")


if __name__ == "__main__":
    main()
