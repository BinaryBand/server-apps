from __future__ import annotations

from enum import StrEnum


class ReconcileState(StrEnum):
    INIT = "init"
    PROBED = "probed"
    APPLYING = "applying"
    VERIFIED = "verified"
    FAILED = "failed"


class IllegalTransitionError(RuntimeError):
    pass


class ReconcileStateMachine:
    _allowed_transitions: dict[ReconcileState, set[ReconcileState]] = {
        ReconcileState.INIT: {
            ReconcileState.PROBED,
            ReconcileState.APPLYING,
            ReconcileState.FAILED,
        },
        ReconcileState.PROBED: {
            ReconcileState.VERIFIED,
            ReconcileState.APPLYING,
            ReconcileState.FAILED,
        },
        ReconcileState.APPLYING: {ReconcileState.PROBED, ReconcileState.FAILED},
        ReconcileState.VERIFIED: set(),
        ReconcileState.FAILED: set(),
    }

    def __init__(self) -> None:
        self.current = ReconcileState.INIT

    def move_to(self, next_state: ReconcileState) -> None:
        if next_state not in self._allowed_transitions[self.current]:
            raise IllegalTransitionError(f"Illegal reconciler transition: {self.current} -> {next_state}")
        self.current = next_state
