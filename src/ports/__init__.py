from typing import Literal, Protocol


class BackupStage(Protocol):
    """Port: a reversible backup/restore operation."""

    def backup(self) -> None: ...

    def restore(self) -> None: ...


class HealthProberPort(Protocol):
    def check_docker(self) -> bool: ...

    def check_containers(self, names: list[str]) -> dict[str, bool]: ...

    def run_all(self) -> None: ...


PermissionsMode = Literal["bootstrap", "runtime", "reset"]


class PermissionsRunnerPort(Protocol):
    def run(self, mode: PermissionsMode, *, dry_run: bool = False) -> None: ...


class ResticRunnerPort(Protocol):
    def ensure_repo(self) -> None: ...

    # underscore-prefixed parameter prevents some dead-code detectors
    # from flagging protocol parameter names as unused symbols.
    def run_backup(self, _excludes: list[str], target: str) -> None: ...

    def run_restore(self, snapshot: str, target: str) -> None: ...

    def list_snapshots(self) -> list[dict]: ...

    def push_to_remote(self, remote: str) -> None: ...


class SecretProviderPort(Protocol):
    def get(self, key: str, default: str = "") -> str: ...


__all__ = [
    "BackupStage",
    "HealthProberPort",
    "PermissionsRunnerPort",
    "ResticRunnerPort",
    "SecretProviderPort",
    "PermissionsMode",
]
