from __future__ import annotations

from collections.abc import Callable
from unittest.mock import Mock


def patch_reconciler_observer(
    monkeypatch,
    *,
    volumes: list[str] | None = None,
    services: list[str] | None = None,
    volume_probe: Callable[[str], bool] | None = None,
    service_probe: Callable[[str], bool] | None = None,
    media_public: bool = True,
) -> None:
    monkeypatch.setattr(
        "src.reconciler.runtime_observer.required_external_volume_names",
        lambda: volumes if volumes is not None else [],
    )
    monkeypatch.setattr(
        "src.reconciler.runtime_observer.compose_service_names",
        lambda: services if services is not None else [],
    )
    monkeypatch.setattr(
        "src.reconciler.runtime_observer.probe_external_volume",
        volume_probe or (lambda _name: True),
    )
    monkeypatch.setattr(
        "src.reconciler.runtime_observer.probe_container_health",
        service_probe or (lambda _name: True),
    )
    monkeypatch.setattr(
        "src.reconciler.runtime_observer.probe_minio_media_public",
        lambda: media_public,
    )


def patch_runtime_pipeline(
    monkeypatch,
    *,
    permissions_side_effect: Exception | None = None,
) -> dict[str, Mock]:
    mocks = {
        "ensure_volumes": Mock(),
        "run_permissions": (
            Mock(side_effect=permissions_side_effect)
            if permissions_side_effect is not None
            else Mock()
        ),
        "run_post_start": Mock(),
        "run_health_checks": Mock(),
    }

    monkeypatch.setattr("src.workflows.pipeline.ensure_external_volumes", mocks["ensure_volumes"])
    monkeypatch.setattr("src.workflows.pipeline.run_permissions_playbook", mocks["run_permissions"])
    monkeypatch.setattr("src.workflows.pipeline.run_runtime_post_start", mocks["run_post_start"])
    monkeypatch.setattr(
        "src.workflows.pipeline.run_runtime_health_checks", mocks["run_health_checks"]
    )
    return mocks
