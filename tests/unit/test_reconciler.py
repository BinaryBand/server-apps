from __future__ import annotations

from src.reconciler.core import reconcile_once
from tests.support.reconciler_helpers import patch_reconciler_observer


def test_check_only_reports_degraded_when_volume_drift_exists(state_root_tmp, monkeypatch) -> None:
    patch_reconciler_observer(
        monkeypatch,
        volumes=["rclone_config"],
        services=[],
        volume_probe=lambda _name: False,
        media_public=True,
    )

    state = reconcile_once(check_only=True)

    assert state.observed == "Degraded"
    assert state.runStatus == "failed"
    condition = next(c for c in state.conditions if c.name == "volume:rclone_config")
    assert condition.status == "false"


def test_check_only_reports_healthy_when_checks_pass(state_root_tmp, monkeypatch) -> None:
    calls: list[str] = []

    def fake_probe(name: str) -> bool:
        calls.append(name)
        return True

    patch_reconciler_observer(
        monkeypatch,
        volumes=[],
        services=["jellyfin"],
        service_probe=fake_probe,
        media_public=True,
    )

    state = reconcile_once(check_only=True)

    assert calls == ["jellyfin"]
    assert state.observed == "Healthy"
    assert state.runStatus == "completed"
    condition = next(c for c in state.conditions if c.name == "service:jellyfin")
    assert condition.status == "true"


def test_check_only_reports_degraded_when_media_bucket_not_public(
    state_root_tmp, monkeypatch
) -> None:
    patch_reconciler_observer(
        monkeypatch,
        volumes=[],
        services=[],
        media_public=False,
    )

    state = reconcile_once(check_only=True)

    assert state.observed == "Degraded"
    assert state.runStatus == "failed"
    condition = next(c for c in state.conditions if c.name == "minio:media-public")
    assert condition.status == "false"


def test_check_only_records_media_public_condition_when_healthy(
    state_root_tmp, monkeypatch
) -> None:
    patch_reconciler_observer(
        monkeypatch,
        volumes=[],
        services=[],
        media_public=True,
    )

    state = reconcile_once(check_only=True)

    assert state.observed == "Healthy"
    condition = next(c for c in state.conditions if c.name == "minio:media-public")
    assert condition.status == "true"
