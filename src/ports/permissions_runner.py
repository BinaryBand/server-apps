from typing import Literal, Protocol

PermissionsMode = Literal["bootstrap", "runtime", "reset"]


class PermissionsRunnerPort(Protocol):
    def run(self, mode: PermissionsMode, *, dry_run: bool = False) -> None: ...
