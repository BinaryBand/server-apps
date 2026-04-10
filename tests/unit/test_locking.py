from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infra.locking import RunbookLock


def test_second_lock_acquire_fails_while_first_is_held() -> None:
    with TemporaryDirectory() as temp_dir:
        first = RunbookLock("start-stop", root=Path(temp_dir))
        second = RunbookLock("start-stop", root=Path(temp_dir))

        first.acquire()
        try:
            with pytest.raises(RuntimeError):
                second.acquire()
        finally:
            first.release()
