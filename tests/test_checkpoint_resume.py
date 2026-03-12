from __future__ import annotations

from src.managers.checkpoint import OperationCheckpoint

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main


class OperationCheckpointTest(TestCase):
    def test_resume_skips_completed_stage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = OperationCheckpoint("start", Path(temp_dir), resume=False)
            first.start(desired="Healthy")
            first.mark_stage("volumes", ok=True)

            resumed = OperationCheckpoint("start", Path(temp_dir), resume=True)
            resumed.start(desired="Healthy")

            self.assertTrue(resumed.should_skip_stage("volumes"))
            self.assertFalse(resumed.should_skip_stage("permissions"))


if __name__ == "__main__":
    main()
