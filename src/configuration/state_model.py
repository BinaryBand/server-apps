from __future__ import annotations

from pydantic import BaseModel, Field

from datetime import datetime, timezone
from typing import Literal


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ConditionStatus = Literal["true", "false", "unknown"]
RunStatus = Literal["in-progress", "completed", "failed"]


class StageCondition(BaseModel):
    name: str
    status: ConditionStatus = "unknown"
    message: str | None = None
    lastTransitionTime: datetime = Field(default_factory=utc_now)


class WorkflowState(BaseModel):
    workflow: str
    desired: str
    observed: str = "Unknown"
    runId: str
    runStatus: RunStatus = "in-progress"
    idempotencyToken: str
    conditions: list[StageCondition] = Field(default_factory=list)
    lastTransitionTime: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
