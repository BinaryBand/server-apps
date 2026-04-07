from __future__ import annotations

from src.configuration.state_model import WorkflowState
from src.reconciler.adapters.pipeline_actions import run_pipeline_stages
from src.reconciler.adapters.state_store import load_state, persist_state
from src.reconciler.domain.state_machine import ReconcileState, ReconcileStateMachine
from src.reconciler.observer.runtime_observer import RuntimeObserver
from src.toolbox.io.state_helpers import upsert_condition


def _has_successful_full_reconcile_markers(state: WorkflowState) -> bool:
    statuses = {condition.name: condition.status for condition in state.conditions}
    required = ("PermissionsApplied", "PostStartApplied")
    return all(statuses.get(name) == "true" for name in required)


def _apply_state_from_probes(state: WorkflowState, any_degraded: bool) -> None:
    observed, run_status = {
        True: ("Degraded", "failed"),
        False: ("Healthy", "completed"),
    }[any_degraded]
    state.observed = observed
    state.runStatus = run_status
    persist_state(state)


def _is_already_healthy(state: WorkflowState) -> bool:
    checks = (
        state.observed == "Healthy",
        state.runStatus == "completed",
        _has_successful_full_reconcile_markers(state),
    )
    return all(checks)


def _refresh_from_observer(state: WorkflowState, observer: RuntimeObserver) -> bool:
    any_degraded = observer.probe_runtime(state)
    _apply_state_from_probes(state, any_degraded)
    return any_degraded


def _apply_runtime_failure(state: WorkflowState, err: RuntimeError) -> WorkflowState:
    upsert_condition(state, "RuntimeHealth", "false", str(err))
    state.observed = "Degraded"
    state.runStatus = "failed"
    persist_state(state)
    return state


def _reconcile_check_only(
    state: WorkflowState,
    observer: RuntimeObserver,
    machine: ReconcileStateMachine,
) -> WorkflowState:
    machine.move_to(ReconcileState.PROBED)
    _refresh_from_observer(state, observer)
    machine.move_to(ReconcileState.VERIFIED)
    return state


def _reconcile_full(
    state: WorkflowState,
    observer: RuntimeObserver,
    machine: ReconcileStateMachine,
) -> WorkflowState:
    machine.move_to(ReconcileState.PROBED)
    if _is_already_healthy(state) and not _refresh_from_observer(state, observer):
        machine.move_to(ReconcileState.VERIFIED)
        return state

    machine.move_to(ReconcileState.APPLYING)
    run_pipeline_stages(state)
    machine.move_to(ReconcileState.PROBED)

    _refresh_from_observer(state, observer)
    machine.move_to(ReconcileState.VERIFIED)
    return state


def reconcile_once(*, check_only: bool = False) -> WorkflowState:
    state: WorkflowState = load_state("Healthy")
    observer = RuntimeObserver()
    machine = ReconcileStateMachine()

    try:
        if check_only:
            return _reconcile_check_only(state, observer, machine)
        return _reconcile_full(state, observer, machine)
    except RuntimeError as err:
        machine.move_to(ReconcileState.FAILED)
        return _apply_runtime_failure(state, err)
