from __future__ import annotations

from unittest.mock import call, patch

from src.adapters.rclone.stream_sync import RcloneStreamSync


def _make_adapter(
    source: str = "minio:",
    destination: str = "pcloud:Backups/Test",
    exclude: list[str] | None = None,
) -> RcloneStreamSync:
    return RcloneStreamSync(
        source=source,
        destination=destination,
        exclude=exclude or [],
    )


def _call_args(adapter: RcloneStreamSync, method: str) -> tuple[tuple, dict]:
    with (
        patch("src.adapters.rclone.stream_sync.volatile") as mock_volatile,
        patch("src.adapters.rclone.stream_sync.storage_docker_mount_flags", return_value=[]),
        patch("src.adapters.rclone.stream_sync.get_project_name", return_value="proj"),
        patch("src.adapters.rclone.stream_sync.rclone_sync") as mock_sync,
    ):
        mock_volatile.rclone_docker_volume_flags.return_value = []
        getattr(adapter, method)()
        return mock_sync.call_args


class TestRcloneStreamSyncBackup:
    def test_backup_passes_source_to_rclone(self) -> None:
        adapter = _make_adapter(source="minio:", destination="pcloud:Backups/X")
        args, kwargs = _call_args(adapter, "backup")
        assert args[0] == "minio:"
        assert args[1] == "pcloud:Backups/X"

    def test_backup_includes_exclude_flags(self) -> None:
        adapter = _make_adapter(exclude=["notes/**"])
        args, kwargs = _call_args(adapter, "backup")
        extra = kwargs["extra_args"]
        assert "--exclude" in extra
        assert "notes/**" in extra


class TestRcloneStreamSyncRestore:
    def test_restore_swaps_source_and_destination(self) -> None:
        adapter = _make_adapter(source="minio:", destination="pcloud:Backups/X")
        args, kwargs = _call_args(adapter, "restore")
        # Restore: cloud → source (direction reversed)
        assert args[0] == "pcloud:Backups/X"
        assert args[1] == "minio:"

    def test_restore_preserves_exclude_patterns(self) -> None:
        adapter = _make_adapter(
            source="minio:",
            destination="pcloud:Backups/Minio",
            exclude=["notes/**"],
        )
        args, kwargs = _call_args(adapter, "restore")
        extra = kwargs["extra_args"]
        assert "--exclude" in extra
        assert "notes/**" in extra

    def test_restore_uses_same_extra_flags_as_backup(self) -> None:
        adapter = _make_adapter()
        backup_args = _call_args(adapter, "backup")[1]["extra_args"]
        restore_args = _call_args(adapter, "restore")[1]["extra_args"]
        assert backup_args == restore_args


class TestRcloneStreamSyncDockerArgs:
    def test_network_flag_included(self) -> None:
        with (
            patch("src.adapters.rclone.stream_sync.volatile") as mock_volatile,
            patch("src.adapters.rclone.stream_sync.storage_docker_mount_flags", return_value=[]),
            patch(
                "src.adapters.rclone.stream_sync.get_project_name",
                return_value="myproject",
            ),
            patch("src.adapters.rclone.stream_sync.rclone_sync") as mock_sync,
        ):
            mock_volatile.rclone_docker_volume_flags.return_value = []
            _make_adapter().backup()
            docker_args = mock_sync.call_args[1]["docker_args"]
            assert "--network" in docker_args
            assert "myproject_default" in docker_args
