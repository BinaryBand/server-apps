from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from src.workflows.checkpoint import OperationCheckpoint


def test_resume_skips_completed_stage() -> None:
    with TemporaryDirectory() as temp_dir:
        first = OperationCheckpoint("start", Path(temp_dir), resume=False)
        first.start(desired="Healthy")
        first.mark_stage("volumes", ok=True)

        resumed = OperationCheckpoint("start", Path(temp_dir), resume=True)
        resumed.start(desired="Healthy")

        assert resumed.should_skip_stage("volumes") is True
        assert resumed.should_skip_stage("permissions") is False
