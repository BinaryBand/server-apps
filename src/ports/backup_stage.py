from typing import Protocol


class BackupStage(Protocol):
    """Port: a reversible backup/restore operation."""

    def backup(self) -> None: ...

    def restore(self) -> None: ...


__all__ = ["BackupStage"]
