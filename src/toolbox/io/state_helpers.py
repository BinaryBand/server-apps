from __future__ import annotations

from datetime import datetime

from src.configuration.state_model import StageCondition, WorkflowState, utc_now


def upsert_condition(
    state: WorkflowState, name: str, status: str, message: str | None = None
) -> None:
    """Upsert a condition into the workflow state and update timestamps.

    This consolidates repeated logic used across reconciler and checkpoints.
    """
    now: datetime = utc_now()
    for idx, condition in enumerate(state.conditions):
        if condition.name != name:
            continue
        state.conditions[idx] = StageCondition(
            name=name, status=status, message=message, lastTransitionTime=now
        )
        break
    else:
        state.conditions.append(
            StageCondition(name=name, status=status, message=message, lastTransitionTime=now)
        )

    state.lastTransitionTime = now
    state.updatedAt = now


__all__ = ["upsert_condition"]
