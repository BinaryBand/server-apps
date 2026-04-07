from __future__ import annotations


from src.reconciler.core import reconcile_once


def test_check_only_reports_degraded_when_volume_drift_exists(
    state_root_tmp, monkeypatch
) -> None:
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.required_external_volume_names",
        lambda: ["rclone_config"],
    )
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.probe_external_volume", lambda name: False
    )
    monkeypatch.setattr("src.reconciler.observer.runtime_observer.compose_service_names", lambda: [])
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
    )

    state = reconcile_once(check_only=True)

    assert state.observed == "Degraded"
    assert state.runStatus == "failed"
    condition = next(c for c in state.conditions if c.name == "volume:rclone_config")
    assert condition.status == "false"


def test_check_only_reports_healthy_when_checks_pass(
    state_root_tmp, monkeypatch
) -> None:
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.required_external_volume_names", lambda: []
    )
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.compose_service_names", lambda: ["jellyfin"]
    )

    calls: list[str] = []

    def fake_probe(name: str) -> bool:
        calls.append(name)
        return True

    monkeypatch.setattr("src.reconciler.observer.runtime_observer.probe_container_health", fake_probe)
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
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
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.required_external_volume_names", lambda: []
    )
    monkeypatch.setattr("src.reconciler.observer.runtime_observer.compose_service_names", lambda: [])
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: False
    )

    state = reconcile_once(check_only=True)

    assert state.observed == "Degraded"
    assert state.runStatus == "failed"
    condition = next(c for c in state.conditions if c.name == "minio:media-public")
    assert condition.status == "false"


def test_check_only_records_media_public_condition_when_healthy(
    state_root_tmp, monkeypatch
) -> None:
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.required_external_volume_names", lambda: []
    )
    monkeypatch.setattr("src.reconciler.observer.runtime_observer.compose_service_names", lambda: [])
    monkeypatch.setattr(
        "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
    )

    state = reconcile_once(check_only=True)

    assert state.observed == "Healthy"
    condition = next(c for c in state.conditions if c.name == "minio:media-public")
    assert condition.status == "true"
