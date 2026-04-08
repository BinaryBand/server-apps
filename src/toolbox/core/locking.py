from __future__ import annotations

from pathlib import Path
import os
import shutil
import time

from typing import Literal


class RunbookLock:
    def __init__(self, name: str, root: Path, *, timeout_seconds: float = 0.0):
        self._name: str = name
        self._root: Path = root
        self._timeout_seconds: float = timeout_seconds
        self._lock_dir: Path = self._root / f"{self._name}.lock"

    def _is_stale(self) -> bool:
        marker: Path = self._lock_dir / "owner.txt"
        try:
            text = marker.read_text(encoding="utf-8")
            pid = int(text.strip().removeprefix("pid="))
        except (FileNotFoundError, ValueError):
            return True
        try:
            os.kill(pid, 0)
            return False
        except ProcessLookupError:
            return True
        except PermissionError:
            return False

    def _ensure_root(self) -> None:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except PermissionError as err:
            raise RuntimeError(f"unable to create lock root: {self._root}") from err

    def _attempt_mkdir(self) -> Literal["acquired", "retry", "held"]:
        try:
            self._lock_dir.mkdir()
            marker: Path = self._lock_dir / "owner.txt"
            marker.write_text(f"pid={os.getpid()}\n", encoding="utf-8")
            return "acquired"
        except PermissionError as err:
            raise RuntimeError(f"unable to acquire lock: {self._lock_dir}") from err
        except FileExistsError:
            if self._is_stale():
                shutil.rmtree(self._lock_dir, ignore_errors=True)
                return "retry"
            return "held"

    def _deadline_passed(self, deadline: float) -> bool:
        return self._timeout_seconds <= 0 or time.monotonic() >= deadline

    def acquire(self) -> None:
        self._ensure_root()
        deadline: float = time.monotonic() + self._timeout_seconds

        while True:
            status = self._attempt_mkdir()
            if status == "acquired":
                return
            if status == "held":
                if self._deadline_passed(deadline):
                    raise RuntimeError(f"lock is held for group '{self._name}' ({self._lock_dir})")
                time.sleep(0.1)

    def release(self) -> None:
        if self._lock_dir.exists():
            shutil.rmtree(self._lock_dir, ignore_errors=True)

    def __enter__(self) -> "RunbookLock":
        self.acquire()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


__all__ = ["RunbookLock"]
