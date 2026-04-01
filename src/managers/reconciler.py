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
    statuses: list[bool] = []
    for volume_name in required_external_volume_names():
        exists = probe_external_volume(volume_name)
        upsert_condition(state, f"volume:{volume_name}", "true" if exists else "false")
        statuses.append(exists)
    return not all(statuses)


def _probe_services(state: WorkflowState) -> bool:
    """Probe container health and return degraded status."""
    statuses: list[bool] = []
    for service_name in compose_service_names():
        healthy = probe_container_health(service_name)
        upsert_condition(
            state, f"service:{service_name}", "true" if healthy else "false"
        )
        statuses.append(healthy)
    return not all(statuses)


def _probe_runtime_conditions(state: WorkflowState) -> bool:
    """Update runtime conditions from current probes and return degraded status."""
    volumes_degraded = _probe_volumes(state)
    services_degraded = _probe_services(state)

    media_public = probe_minio_media_public()
    upsert_condition(state, "minio:media-public", "true" if media_public else "false")

    return any((volumes_degraded, services_degraded, not media_public))


def _has_successful_full_reconcile_markers(state: WorkflowState) -> bool:
    statuses = {condition.name: condition.status for condition in state.conditions}
    required = ("PermissionsApplied", "PostStartApplied")
    return all(statuses.get(name) == "true" for name in required)


def _apply_state_from_probes(state: WorkflowState, any_degraded: bool) -> None:
    """Update state from probe results and persist."""
    observed, run_status = {
        True: ("Degraded", "failed"),
        False: ("Healthy", "completed"),
    }[any_degraded]
    state.observed = observed
    state.runStatus = run_status
    _persist_state(state)


def _is_already_healthy(state: WorkflowState) -> bool:
    """Check if state indicates prior healthy completion."""
    checks = (
        state.observed == "Healthy",
        state.runStatus == "completed",
        _has_successful_full_reconcile_markers(state),
    )
    return all(checks)


def _mark_stage_conditions(state: WorkflowState, stage_name: str) -> None:
    """Mark conditions after a pipeline stage executes."""
    builders: dict[str, Any] = {
        "volumes": lambda: [
            f"volume:{name}" for name in required_external_volume_names()
        ],
        "permissions": lambda: ["PermissionsApplied"],
        "runtime": lambda: ["PostStartApplied", "minio:media-public"],
        "health": lambda: [f"service:{name}" for name in compose_service_names()],
    }
    names = builders.get(stage_name, lambda: [])()

    for name in names:
        upsert_condition(state, name, "true")


def _run_pipeline_stages(state: WorkflowState) -> None:
    """Execute pipeline stages and mark conditions."""
    for stage_name, step in PIPELINE_STEPS:
        step()
        _mark_stage_conditions(state, stage_name)


def _refresh_from_probes(state: WorkflowState) -> bool:
    any_degraded = _probe_runtime_conditions(state)
    _apply_state_from_probes(state, any_degraded)
    return any_degraded


def _reconcile_check_only(state: WorkflowState) -> WorkflowState:
    _refresh_from_probes(state)
    return state


def _reconcile_full(state: WorkflowState) -> WorkflowState:
    # Full reconcile is idempotent: if the last state was healthy and probes
    # still pass, return without replaying mutating pipeline steps.
    if _is_already_healthy(state) and not _refresh_from_probes(state):
        return state

    _run_pipeline_stages(state)
    _refresh_from_probes(state)
    return state


def _apply_runtime_failure(state: WorkflowState, err: RuntimeError) -> WorkflowState:
    upsert_condition(state, "RuntimeHealth", "false", str(err))
    state.observed = "Degraded"
    state.runStatus = "failed"
    _persist_state(state)
    return state


def reconcile_once(*, check_only: bool = False) -> WorkflowState:
    state: WorkflowState = _load_state("Healthy")

    try:
        if check_only:
            return _reconcile_check_only(state)
        return _reconcile_full(state)
    except RuntimeError as err:
        return _apply_runtime_failure(state, err)
