from __future__ import annotations

from src.toolbox.core.locking import RunbookLock

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main


class RunbookLockTest(TestCase):
    def test_second_lock_acquire_fails_while_first_is_held(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = RunbookLock("start-stop", root=Path(temp_dir))
            second = RunbookLock("start-stop", root=Path(temp_dir))

            first.acquire()
            try:
                with self.assertRaises(RuntimeError):
                    second.acquire()
            finally:
                first.release()


if __name__ == "__main__":
    main()
