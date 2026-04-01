from __future__ import annotations

from src.configuration.state_model import WorkflowState, utc_now
from src.managers.pipeline import PIPELINE_STEPS
from src.toolbox.docker.compose import (
    compose_service_names,
    probe_external_volume,
)
from src.toolbox.docker.health import probe_container_health, probe_minio_media_public
from src.toolbox.docker.volumes import required_external_volume_names
from src.toolbox.core.runtime import state_root
from src.toolbox.io.state_io import read_json_file, write_json_file_atomic

from typing import Any
from pathlib import Path
from uuid import uuid4
from src.toolbox.io.state_helpers import upsert_condition


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
    state.updatedAt = utc_now()
    return state


def _persist_state(state: WorkflowState) -> None:
    path: Path = state_root() / "reconcile.json"
    write_json_file_atomic(path, state.model_dump(mode="json"))


def _probe_volumes(state: WorkflowState) -> bool:
    """Probe external volumes and return degraded status."""
    any_degraded = False
    for volume_name in required_external_volume_names():
        exists = probe_external_volume(volume_name)
        upsert_condition(state, f"volume:{volume_name}", "true" if exists else "false")
        if not exists:
            any_degraded = True
    return any_degraded


def _probe_services(state: WorkflowState) -> bool:
    """Probe container health and return degraded status."""
    any_degraded = False
    for service_name in compose_service_names():
        healthy = probe_container_health(service_name)
        upsert_condition(state, f"service:{service_name}", "true" if healthy else "false")
        if not healthy:
            any_degraded = True
    return any_degraded


def _probe_runtime_conditions(state: WorkflowState) -> bool:
    """Update runtime conditions from current probes and return degraded status."""
    volumes_degraded = _probe_volumes(state)
    services_degraded = _probe_services(state)

    media_public = probe_minio_media_public()
    upsert_condition(
        state, "minio:media-public", "true" if media_public else "false"
    )

    return volumes_degraded or services_degraded or not media_public


def _has_successful_full_reconcile_markers(state: WorkflowState) -> bool:
    statuses = {condition.name: condition.status for condition in state.conditions}
    return (
        statuses.get("PermissionsApplied") == "true"
        and statuses.get("PostStartApplied") == "true"
    )


def _apply_state_from_probes(state: WorkflowState, any_degraded: bool) -> None:
    """Update state from probe results and persist."""
    state.observed = "Degraded" if any_degraded else "Healthy"
    state.runStatus = "failed" if any_degraded else "completed"
    _persist_state(state)


def _is_already_healthy(state: WorkflowState) -> bool:
    """Check if state indicates prior healthy completion."""
    return (
        state.observed == "Healthy"
        and state.runStatus == "completed"
        and _has_successful_full_reconcile_markers(state)
    )


def _mark_stage_conditions(state: WorkflowState, stage_name: str) -> None:
    """Mark conditions after a pipeline stage executes."""
    if stage_name == "volumes":
        for volume_name in required_external_volume_names():
            upsert_condition(state, f"volume:{volume_name}", "true")
    elif stage_name == "permissions":
        upsert_condition(state, "PermissionsApplied", "true")
    elif stage_name == "runtime":
        upsert_condition(state, "PostStartApplied", "true")
        upsert_condition(state, "minio:media-public", "true")
    elif stage_name == "health":
        for service_name in compose_service_names():
            upsert_condition(state, f"service:{service_name}", "true")


def _run_pipeline_stages(state: WorkflowState) -> None:
    """Execute pipeline stages and mark conditions."""
    for stage_name, step in PIPELINE_STEPS:
        step()
        _mark_stage_conditions(state, stage_name)


def reconcile_once(*, check_only: bool = False) -> WorkflowState:
    state: WorkflowState = _load_state("Healthy")

    try:
        if check_only:
            any_degraded = _probe_runtime_conditions(state)
            _apply_state_from_probes(state, any_degraded)
            return state

        # Full reconcile is idempotent: if the last state was healthy and probes
        # still pass, return without replaying mutating pipeline steps.
        if _is_already_healthy(state):
            any_degraded = _probe_runtime_conditions(state)
            _apply_state_from_probes(state, any_degraded)
            if not any_degraded:
                return state

        _run_pipeline_stages(state)

        any_degraded = _probe_runtime_conditions(state)
        _apply_state_from_probes(state, any_degraded)
        return state
    except RuntimeError as err:
        upsert_condition(state, "RuntimeHealth", "false", str(err))
        state.observed = "Degraded"
        state.runStatus = "failed"
        _persist_state(state)
        return state
