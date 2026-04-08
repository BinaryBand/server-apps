from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class StreamSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source: str
    destination: str
    exclude: list[str] = Field(default_factory=list)


class CompressSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    source: str
    patterns: list[str]
    destination: str


class BatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class BackupConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch: BatchConfig = Field(default_factory=BatchConfig)
    stream: list[StreamSource] = Field(default_factory=list)
    compress: list[CompressSource] = Field(default_factory=list)

    @classmethod
    def from_toml(cls, path: Path) -> BackupConfig:
        with open(path, "rb") as f:
            return cls.model_validate(tomllib.load(f))


__all__ = ["BackupConfig", "BatchConfig", "CompressSource", "StreamSource"]
