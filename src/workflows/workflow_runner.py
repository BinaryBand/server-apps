from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from src.workflows.checkpoint import OperationCheckpoint


@dataclass(frozen=True)
class StagePolicy:
    observed_on_failure: str
    run_message: str | None = None
    error_prefix: str | None = None
    handled_exceptions: tuple[type[Exception], ...] = (RuntimeError,)


def start_checkpoint(
    workflow: str,
    desired: str,
    *,
    root: Path,
    resume: bool,
) -> OperationCheckpoint:
    checkpoint = OperationCheckpoint(workflow, root, resume=resume)
    checkpoint.start(desired=desired)
    return checkpoint


def fail_checkpoint_stage(
    checkpoint: OperationCheckpoint,
    stage_name: str,
    err: Exception,
    policy: StagePolicy,
) -> None:
    checkpoint.mark_stage(stage_name, ok=False, message=str(err))
    checkpoint.finish(observed=policy.observed_on_failure, ok=False)
    prefix = policy.error_prefix or stage_name
    raise SystemExit(f"[stage:{prefix}] {err}") from err


def _run_stage_step(
    step: Callable[[], None],
    handled_exceptions: tuple[type[Exception], ...],
) -> Exception | None:
    try:
        step()
    except handled_exceptions as err:
        return err
    return None


def run_checkpoint_stage(
    checkpoint: OperationCheckpoint,
    stage_name: str,
    step: Callable[[], None],
    policy: StagePolicy,
) -> None:
    if checkpoint.should_skip_stage(stage_name):
        print(f"[stage:{stage_name}] Skipping already completed stage")
        return
    print(policy.run_message or f"[stage:{stage_name}] Running...")
    if err := _run_stage_step(step, policy.handled_exceptions):
        fail_checkpoint_stage(
            checkpoint,
            stage_name,
            err=err,
            policy=policy,
        )

    checkpoint.mark_stage(stage_name, ok=True)


def run_checkpoint_stages(
    checkpoint: OperationCheckpoint,
    stages: Iterable[tuple[str, Callable[[], None]]],
    *,
    observed_on_failure: str,
) -> None:
    policy = StagePolicy(observed_on_failure=observed_on_failure)
    for stage_name, step in stages:
        run_checkpoint_stage(
            checkpoint,
            stage_name,
            step,
            policy,
        )


__all__ = [
    "StagePolicy",
    "start_checkpoint",
    "fail_checkpoint_stage",
    "run_checkpoint_stage",
    "run_checkpoint_stages",
]
