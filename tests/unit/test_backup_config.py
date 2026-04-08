from __future__ import annotations

import textwrap
import tomllib

import pytest
from pydantic import ValidationError

from src.configuration.backup_config import BackupConfig


def _parse(toml: str) -> BackupConfig:
    return BackupConfig.model_validate(tomllib.loads(textwrap.dedent(toml)))


class TestBackupConfigParsing:
    def test_minimal_config(self) -> None:
        config = _parse("")
        assert config.batch.include == []
        assert config.batch.exclude == []
        assert config.stream == []

    def test_batch_include_and_exclude(self) -> None:
        config = _parse("""
            [batch]
            include = ["volumes/foo/**"]
            exclude = ["volumes/foo/tmp/**"]
        """)
        assert config.batch.include == ["volumes/foo/**"]
        assert config.batch.exclude == ["volumes/foo/tmp/**"]

    def test_stream_source_defaults(self) -> None:
        config = _parse("""
            [[stream]]
            name = "my-stream"
            source = "minio:"
            destination = "pcloud:Backups/Test"
        """)
        assert len(config.stream) == 1
        s = config.stream[0]
        assert s.name == "my-stream"
        assert s.source == "minio:"
        assert s.destination == "pcloud:Backups/Test"
        assert s.exclude == []

    def test_stream_source_with_exclude(self) -> None:
        config = _parse("""
            [[stream]]
            name = "minio-objects"
            source = "minio:"
            destination = "pcloud:Backups/Minio"
            exclude = ["notes/**"]
        """)
        assert config.stream[0].exclude == ["notes/**"]

    # compress entries removed from configuration model; related tests removed

    def test_multiple_streams(self) -> None:
        config = _parse("""
            [[stream]]
            name = "a"
            source = "minio:"
            destination = "pcloud:A"

            [[stream]]
            name = "b"
            source = "/data/volumes/foo"
            destination = "pcloud:B"
        """)
        assert len(config.stream) == 2
        assert config.stream[0].name == "a"
        assert config.stream[1].name == "b"

    def test_extra_keys_rejected_on_batch(self) -> None:
        with pytest.raises(ValidationError):
            _parse("""
                [batch]
                include = []
                unknown_key = "oops"
            """)

    def test_extra_keys_rejected_on_stream(self) -> None:
        with pytest.raises(ValidationError):
            _parse("""
                [[stream]]
                name = "x"
                source = "s"
                destination = "d"
                typo_field = true
            """)

    # compress-related tests removed
