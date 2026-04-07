from __future__ import annotations

from src.managers.pipeline import PIPELINE_STEPS


def test_pipeline_step_order_excludes_media_sync() -> None:
    stages = [name for name, _ in PIPELINE_STEPS]
    assert stages == ["volumes", "permissions", "runtime", "health"]
