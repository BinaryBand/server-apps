from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def pytest_collection_modifyitems(session, config, items):
    """Run the quality-gate tests first so pytest fails fast on lint/quality issues.

    This moves any test with `test_quality_gate` in the nodeid to the front of
    the collected items list.
    """
    priority = [i for i in items if "test_quality_gate" in i.nodeid]
    rest = [i for i in items if "test_quality_gate" not in i.nodeid]
    items[:] = priority + rest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def docker_available() -> bool:
    return shutil.which("docker") is not None


@pytest.fixture
def assert_helpers():
    from tests.support import asserts

    return asserts


@pytest.fixture
def state_root_tmp(monkeypatch, tmp_path: Path) -> Path:
    """Provide a temporary state root and patch the reconciler to use it.

    Tests can depend on this fixture to ensure isolated state for idempotency checks.
    """
    monkeypatch.setattr("src.reconciler.state_store.state_root", lambda: tmp_path)
    return tmp_path
