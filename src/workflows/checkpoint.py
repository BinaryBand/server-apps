from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from src.configuration.state_model import WorkflowState, utc_now
from src.infra.io.state_io import read_json_file, write_json_file_atomic

# Module-level sentinel for completed stage status
_STAGE_COMPLETE: str = "true"


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

        return any(c.name == stage_name and c.status == _STAGE_COMPLETE for c in state.conditions)

    def mark_stage(self, stage_name: str, *, ok: bool, message: str | None = None) -> None:
        from src.infra.io.state_helpers import upsert_condition

        state: WorkflowState = self.state
        status: Literal["true", "false"] = "true" if ok else "false"

        upsert_condition(state, stage_name, status, message)
        self._persist()

    def finish(self, *, observed: str, ok: bool) -> None:
        state: WorkflowState = self.state
        now = utc_now()
        state.observed = observed
        state.runStatus = "completed" if ok else "failed"
        state.updatedAt = now
        state.lastTransitionTime = now
        self._persist()

    def _persist(self) -> None:
        state: WorkflowState = self.state
        write_json_file_atomic(self._path, state.model_dump(mode="json"))

    def _load(self) -> WorkflowState | None:
        raw: Any = read_json_file(self._path)
        if raw is None:
            return None
        return WorkflowState.model_validate(raw)
