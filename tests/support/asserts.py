from __future__ import annotations

from typing import Callable


def assert_state_condition(state, name: str, status: str) -> None:
    condition = next((c for c in state.conditions if c.name == name), None)
    assert condition is not None, f"Condition {name} not found on state"
    assert condition.status == status


def assert_idempotent(run_once: Callable[..., object], *args, **kwargs) -> None:
    """Run the provided callable twice and assert the second run makes no further changes.

    The callable must return an object representing state; equality semantics are up
    to the caller. This helper simply runs twice and asserts equality.
    """
    first = run_once(*args, **kwargs)
    second = run_once(*args, **kwargs)
    assert first == second
