from __future__ import annotations

from pathlib import Path
import os
import shutil
import time


class RunbookLockError(RuntimeError):
    pass


class RunbookLock:
    def __init__(self, name: str, root: Path, *, timeout_seconds: float = 0.0):
        self._name = name
        self._root = root
        self._timeout_seconds = timeout_seconds
        self._lock_dir = self._root / f"{self._name}.lock"

    def acquire(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self._timeout_seconds

        while True:
            try:
                self._lock_dir.mkdir()
                marker = self._lock_dir / "owner.txt"
                marker.write_text(f"pid={os.getpid()}\n", encoding="utf-8")
                return
            except FileExistsError:
                if self._timeout_seconds <= 0 or time.monotonic() >= deadline:
                    raise RunbookLockError(
                        f"lock is held for group '{self._name}' ({self._lock_dir})"
                    )
                time.sleep(0.1)

    def release(self) -> None:
        if self._lock_dir.exists():
            shutil.rmtree(self._lock_dir, ignore_errors=True)

    def __enter__(self) -> "RunbookLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
