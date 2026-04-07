from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StreamSource:
    name: str
    source: str
    destination: str


@dataclass
class BatchConfig:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass
class BackupConfig:
    batch: BatchConfig = field(default_factory=BatchConfig)
    stream: list[StreamSource] = field(default_factory=list)

    @classmethod
    def from_toml(cls, path: Path) -> BackupConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        b = data.get("batch", {})
        return cls(
            batch=BatchConfig(
                include=b.get("include", []),
                exclude=b.get("exclude", []),
            ),
            stream=[
                StreamSource(
                    name=s["name"],
                    source=s["source"],
                    destination=s["destination"],
                )
                for s in data.get("stream", [])
            ],
        )


__all__ = ["BackupConfig", "BatchConfig", "StreamSource"]
