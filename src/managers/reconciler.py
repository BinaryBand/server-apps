from __future__ import annotations

from src.configuration.state_model import ConditionStatus, StageCondition, WorkflowState
from src.toolbox.docker.compose import ensure_external_volumes, missing_external_volumes
from src.toolbox.docker.health import run_runtime_health_checks
from src.toolbox.docker.post_start import run_runtime_post_start
from src.toolbox.core.ansible import run_permissions_playbook
from src.toolbox.core.runtime import state_root
from src.toolbox.io.state_io import read_json_file, write_json_file_atomic

from datetime import datetime, timezone
from typing import Any, Literal
from pathlib import Path
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_state(desired: str) -> WorkflowState:
    return WorkflowState(
        workflow="reconcile",
        desired=desired,
        observed="Unknown",
        runId=str(uuid4()),
        idempotencyToken=str(uuid4()),
        runStatus="in-progress",
    )


def _load_state(desired: str) -> WorkflowState:
    path: Path = state_root() / "reconcile.json"
    payload: Any = read_json_file(path)
    if payload is None:
        return _new_state(desired)
    state: WorkflowState = WorkflowState.model_validate(payload)
    state.runId = str(uuid4())
    state.idempotencyToken = str(uuid4())
    state.runStatus = "in-progress"
    state.updatedAt: datetime = _utc_now()
    return state


def _upsert_condition(
    state: WorkflowState, name: str, status: ConditionStatus, message: str | None = None
) -> None:
    now: datetime = _utc_now()
    for idx, condition in enumerate(state.conditions):
        if condition.name != name:
            continue
        state.conditions[idx] = StageCondition(
            name=name, status=status, message=message, lastTransitionTime=now
        )
        break
    else:
        state.conditions.append(
            StageCondition(
                name=name, status=status, message=message, lastTransitionTime=now
            )
        )
    state.lastTransitionTime: datetime = now
    state.updatedAt: datetime = now


def _persist_state(state: WorkflowState) -> None:
    path: Path = state_root() / "reconcile.json"
    write_json_file_atomic(path, state.model_dump(mode="json"))


def reconcile_once(*, check_only: bool = False) -> WorkflowState:
    state: WorkflowState = _load_state("Healthy")

    try:
        if check_only:
            missing: list[str] = missing_external_volumes()
            if missing:
                message: str = "Missing external volumes: " + ", ".join(sorted(missing))
                _upsert_condition(state, "VolumesReady", "false", message)
                state.observed: str = "Degraded"
                state.runStatus: Literal["completed", "failed"] = "failed"
                _persist_state(state)
                return state

            run_runtime_health_checks()
            _upsert_condition(state, "VolumesReady", "true")
            _upsert_condition(state, "RuntimeHealth", "true", "all checks passed")
            state.observed = "Healthy"
            state.runStatus = "completed"
            _persist_state(state)
            return state

        ensure_external_volumes()
        _upsert_condition(state, "VolumesReady", "true")

        run_permissions_playbook(mode="runtime")
        _upsert_condition(state, "PermissionsApplied", "true")

        run_runtime_post_start()
        _upsert_condition(state, "PostStartApplied", "true")

        run_runtime_health_checks()
        _upsert_condition(state, "RuntimeHealth", "true", "all runtime checks passed")

        state.observed = "Healthy"
        state.runStatus = "completed"
        _persist_state(state)
        return state
    except RuntimeError as err:
        _upsert_condition(state, "RuntimeHealth", "false", str(err))
        state.observed = "Degraded"
        state.runStatus = "failed"
        _persist_state(state)
        raise
