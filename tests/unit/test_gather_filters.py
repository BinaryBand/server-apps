from __future__ import annotations

from unittest.mock import call, patch

from src.backup.gather import gather_stage


def _captured_extra_args(include: list[str], exclude: list[str]) -> list[str]:
    """Run gather_stage and return the extra_args passed to rclone_sync."""
    with (
        patch("src.backup.gather.volatile") as mock_volatile,
        patch("src.backup.gather.rclone_sync") as mock_sync,
    ):
        mock_volatile.rclone_docker_volume_flags.return_value = []
        mock_volatile.storage_docker_mount_flags.return_value = []
        gather_stage(include, exclude)
        _, kwargs = mock_sync.call_args
        return kwargs["extra_args"]


class TestGatherFilterOrder:
    def test_excludes_come_before_includes(self) -> None:
        """Exclude rules must precede include rules so specific exclusions win."""
        args = _captured_extra_args(
            include=["volumes/minio_data/**"],
            exclude=["volumes/minio_data/.minio.sys/tmp/**"],
        )
        exclude_idx = args.index("- volumes/minio_data/.minio.sys/tmp/**")
        include_idx = args.index("+ volumes/minio_data/**")
        assert exclude_idx < include_idx

    def test_catch_all_exclude_is_last(self) -> None:
        """The catch-all '- *' must be the final filter."""
        args = _captured_extra_args(
            include=["volumes/foo/**"],
            exclude=["volumes/foo/tmp/**"],
        )
        assert args[-1] == "- *"

    def test_all_args_use_filter_flag(self) -> None:
        """No --include or --exclude flags; only --filter."""
        args = _captured_extra_args(
            include=["volumes/foo/**"],
            exclude=["volumes/foo/tmp/**"],
        )
        filter_positions = [i for i, a in enumerate(args) if a == "--filter"]
        non_filter = [a for a in args if a.startswith("--") and a != "--filter"]
        assert len(filter_positions) > 0
        assert non_filter == []

    def test_empty_exclude_still_emits_catch_all(self) -> None:
        args = _captured_extra_args(include=["volumes/foo/**"], exclude=[])
        assert "- *" in args
        assert "+ volumes/foo/**" in args

    def test_filter_values_are_prefixed_correctly(self) -> None:
        args = _captured_extra_args(
            include=["volumes/inc/**"],
            exclude=["volumes/exc/**"],
        )
        # Collect the values that follow --filter flags
        values = [args[i + 1] for i, a in enumerate(args) if a == "--filter"]
        assert any(v.startswith("- ") for v in values)
        assert any(v.startswith("+ ") for v in values)
