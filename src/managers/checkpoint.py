from __future__ import annotations

from typing import Any as Unknown
from typing import Literal

from src.configuration.state_model import StageCondition, WorkflowState
from src.toolbox.io.state_io import read_json_file, write_json_file_atomic

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OperationCheckpoint:
    def __init__(self, workflow: str, root: Path, *, resume: bool = False):
        self._workflow: str = workflow
        self._root: Path = root
        self._resume: bool = resume
        self._path: Path = self._root / f"{self._workflow}.json"
        self._state: WorkflowState | None = None

    @property
    def state(self) -> WorkflowState:
        if self._state is None:
            raise RuntimeError("checkpoint state has not been initialized")
        return self._state

    def start(self, *, desired: str) -> WorkflowState:
        loaded: WorkflowState | None = self._load()
        if self._resume and loaded is not None and loaded.runStatus == "in-progress":
            self._state: WorkflowState = loaded
            return loaded

        self._state = WorkflowState(
            workflow=self._workflow,
            desired=desired,
            runId=str(uuid4()),
            idempotencyToken=str(uuid4()),
            runStatus="in-progress",
        )
        self._persist()
        return self._state

    def should_skip_stage(self, stage_name: str) -> bool:
        if not self._resume:
            return False

        state: WorkflowState = self.state
        if state.runStatus != "in-progress":
            return False

        for condition in state.conditions:
            if condition.name == stage_name and condition.status == "true":
                return True
        return False

    def mark_stage(
        self, stage_name: str, *, ok: bool, message: str | None = None
    ) -> None:
        state: WorkflowState = self.state
        status: Literal["true", "false"] = "true" if ok else "false"
        now: datetime = _utc_now()

        for idx, condition in enumerate(state.conditions):
            if condition.name != stage_name:
                continue
            state.conditions[idx] = StageCondition(
                name=stage_name, status=status, message=message, lastTransitionTime=now
            )
            break
        else:
            state.conditions.append(
                StageCondition(
                    name=stage_name,
                    status=status,
                    message=message,
                    lastTransitionTime=now,
                )
            )

        state.updatedAt = now
        state.lastTransitionTime = now
        self._persist()

    def finish(self, *, observed: str, ok: bool) -> None:
        state: WorkflowState = self.state
        now: datetime = _utc_now()
        state.observed: str = observed
        state.runStatus: Literal["completed", "failed"] = (
            "completed" if ok else "failed"
        )
        state.updatedAt: datetime = now
        state.lastTransitionTime: datetime = now
        self._persist()

    def _persist(self) -> None:
        state: WorkflowState = self.state
        write_json_file_atomic(self._path, state.model_dump(mode="json"))

    def _load(self) -> WorkflowState | None:
        raw: Unknown = read_json_file(self._path)
        if raw is None:
            return None
        return WorkflowState.model_validate(raw)
