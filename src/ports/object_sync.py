from typing import Protocol


class CloudObjectSync(Protocol):
    """Port: synchronize an object store to a remote destination."""

    def sync(self) -> None: ...


__all__ = ["CloudObjectSync"]
