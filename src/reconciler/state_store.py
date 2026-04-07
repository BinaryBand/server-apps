from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from src.configuration.state_model import WorkflowState, utc_now
from src.toolbox.core.runtime import state_root
from src.toolbox.io.state_io import read_json_file, write_json_file_atomic


def _new_state(desired: str) -> WorkflowState:
    return WorkflowState(
        workflow="reconcile",
        desired=desired,
        observed="Unknown",
        runId=str(uuid4()),
        idempotencyToken=str(uuid4()),
        runStatus="in-progress",
    )


def load_state(desired: str) -> WorkflowState:
    path: Path = state_root() / "reconcile.json"
    payload: Any = read_json_file(path)
    if payload is None:
        return _new_state(desired)
    state: WorkflowState = WorkflowState.model_validate(payload)
    state.runId = str(uuid4())
    state.idempotencyToken = str(uuid4())
    state.updatedAt = utc_now()
    return state


def persist_state(state: WorkflowState) -> None:
    path: Path = state_root() / "reconcile.json"
    write_json_file_atomic(path, state.model_dump(mode="json"))
