from __future__ import annotations

from src.configuration.state_model import WorkflowState
from src.toolbox.docker.compose import (
    compose_service_names,
    ensure_external_volumes,
    probe_external_volume,
)
from src.toolbox.docker.health import probe_container_health, run_runtime_health_checks
from src.toolbox.docker.post_start import run_runtime_post_start
from src.toolbox.docker.post_start.minio import probe_minio_media_public
from src.toolbox.docker.volumes import required_external_volume_names
from src.toolbox.core.ansible import run_permissions_playbook
from src.toolbox.core.runtime import state_root
from src.toolbox.io.state_io import read_json_file, write_json_file_atomic

from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from uuid import uuid4
from src.toolbox.io.state_helpers import upsert_condition


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


def _persist_state(state: WorkflowState) -> None:
    path: Path = state_root() / "reconcile.json"
    write_json_file_atomic(path, state.model_dump(mode="json"))


def reconcile_once(*, check_only: bool = False) -> WorkflowState:
    state: WorkflowState = _load_state("Healthy")

    try:
        if check_only:
            any_degraded = False

            for volume_name in required_external_volume_names():
                exists = probe_external_volume(volume_name)
                upsert_condition(
                    state, f"volume:{volume_name}", "true" if exists else "false"
                )
                if not exists:
                    any_degraded = True

            for service_name in compose_service_names():
                healthy = probe_container_health(service_name)
                upsert_condition(
                    state, f"service:{service_name}", "true" if healthy else "false"
                )
                if not healthy:
                    any_degraded = True

            media_public = probe_minio_media_public()
            upsert_condition(
                state, "minio:media-public", "true" if media_public else "false"
            )
            if not media_public:
                any_degraded = True

            state.observed = "Degraded" if any_degraded else "Healthy"
            state.runStatus = "failed" if any_degraded else "completed"
            _persist_state(state)
            return state

        ensure_external_volumes()
        for volume_name in required_external_volume_names():
            upsert_condition(state, f"volume:{volume_name}", "true")

        run_permissions_playbook(mode="runtime")
        upsert_condition(state, "PermissionsApplied", "true")

        run_runtime_post_start()
        upsert_condition(state, "PostStartApplied", "true")
        upsert_condition(state, "minio:media-public", "true")

        run_runtime_health_checks()
        for service_name in compose_service_names():
            upsert_condition(state, f"service:{service_name}", "true")

        state.observed = "Healthy"
        state.runStatus = "completed"
        _persist_state(state)
        return state
    except RuntimeError as err:
        upsert_condition(state, "RuntimeHealth", "false", str(err))
        state.observed = "Degraded"
        state.runStatus = "failed"
        _persist_state(state)
        raise
