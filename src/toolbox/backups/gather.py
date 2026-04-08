from __future__ import annotations

import src.backup.gather as _impl

# Compatibility aliases for legacy monkeypatch targets.
rclone_sync = _impl.rclone_sync
volatile = _impl.volatile


def gather_stage(include_file):
    _impl.rclone_sync = rclone_sync
    _impl.volatile = volatile
    return _impl.gather_stage(include_file)


__all__ = ["gather_stage"]
