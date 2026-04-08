from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class RcloneConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remote: str = Field(default="pcloud")
    version: str = Field(default="latest")
    transfers: int = Field(default=4)
    buffer_size: str = Field(default="64M")
    retries: int = Field(default=3)
    low_level_retries: int = Field(default=5)
    stats: str = Field(default="60s")

    @classmethod
    def from_toml(cls, path: Path) -> "RcloneConfig":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        # Allow either top-level keys or nested [rclone] table
        if isinstance(data, dict) and "rclone" in data and isinstance(data["rclone"], dict):
            data = data["rclone"]
        return cls.model_validate(data)


__all__ = ["RcloneConfig"]
