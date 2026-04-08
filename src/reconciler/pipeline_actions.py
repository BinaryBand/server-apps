from __future__ import annotations

from collections.abc import Callable

from src.configuration.state_model import WorkflowState
from src.storage.compose import compose_service_names
from src.storage.volumes import required_external_volume_names
from src.toolbox.io.state_helpers import upsert_condition
from src.workflows.pipeline import PIPELINE_STEPS


def _mark_stage_conditions(state: WorkflowState, stage_name: str) -> None:
    builders: dict[str, Callable[[], list[str]]] = {
        "volumes": lambda: [f"volume:{name}" for name in required_external_volume_names()],
        "permissions": lambda: ["PermissionsApplied"],
        "runtime": lambda: ["PostStartApplied", "minio:media-public"],
        "health": lambda: [f"service:{name}" for name in compose_service_names()],
    }
    names = builders.get(stage_name, lambda: [])()

    for name in names:
        upsert_condition(state, name, "true")


def run_pipeline_stages(state: WorkflowState) -> None:
    for stage_name, step in PIPELINE_STEPS:
        step()
        _mark_stage_conditions(state, stage_name)
