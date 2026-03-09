from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ComposeVolumeDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    external: bool | dict[str, object] | None = None
    name: str | None = None


class ComposeServiceVolumeMount(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str | None = None
    target: str | None = None


class ComposeServiceDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    volumes: list[str | ComposeServiceVolumeMount] | None = None


class ComposeConfigModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    volumes: dict[str, ComposeVolumeDefinition] = {}
    services: dict[str, ComposeServiceDefinition] = {}
