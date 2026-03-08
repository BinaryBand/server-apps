"""High-level restic manager (orchestration) for backups.

This module acts as the manager layer: it orchestrates high-level backup
operations and delegates low-level command construction and execution to the
`src.utils.docker.wrappers.restic` toolbox. The manager keeps stage-level
behaviour, contextual error messages, and explicit function arguments.

Design notes (per .github/copilot-instructions.md):
- Toolbox (low-level) code lives in `src.utils.docker.wrappers.restic`.
- This module performs orchestration and boundary-aware error handling.
"""

from __future__ import annotations

from typing import List

from src.utils.docker.wrappers import restic as _restic


class ResticManagerError(RuntimeError):
    """Raised for high-level restic orchestration failures.

    This is raised by the manager to provide stage-aware, actionable messages
    to callers. The underlying toolbox raises `_restic.ResticRunnerError`
    for low-level failures.
    """


# Keep compatibility: expose the manager error under the historical name
# `ResticRunnerError` so callers that import it from
# `src.backups.restic_runner` do not need changes.
ResticRunnerError = ResticManagerError


def has_restic_repository(project: str | None = None) -> bool:
    """Return True when the restic repository is already initialized.

    This delegates to the toolbox; any low-level errors are interpreted as
    "not initialized" and surfaced to the caller as False. This keeps the
    check idempotent.
    """
    try:
        return _restic.has_restic_repository()
    except _restic.ResticRunnerError:
        return False


def initialize_restic_repository(project: str | None = None) -> None:
    """Ensure the restic repository is initialized.

    Args are explicit to keep override points visible to runbooks. This
    function raises `ResticManagerError` with context if initialization fails.
    """
    try:
        _restic.initialize_restic_repository()
    except _restic.ResticRunnerError as err:
        raise ResticManagerError(f"[stage:restic-init] {err}") from err


def run_backup(
    paths: List[str] | None = None,
    restic_args: List[str] | None = None,
    project: str | None = None,
) -> None:
    """Run a restic backup of `paths` and optionally push to remote.

    - `paths`: list of paths inside the restic container to snapshot (default: ['/backups']).
    - `restic_args`: extra restic CLI args appended to the `backup` command.
    - `project`: explicit project name for resolution; manager currently uses
      global defaults when not provided.

    This function orchestrates the snapshot stage and captures toolbox
    errors to present stage-aware messages to callers.
    """
    try:
        _restic.run_backup(paths=paths, restic_args=restic_args)
    except _restic.ResticRunnerError as err:
        raise ResticManagerError(f"[stage:restic-backup] {err}") from err


def run_restic_command(cmd_args: List[str]) -> None:
    """Pass-through for low-level command execution (rarely used by runbooks)."""
    try:
        _restic.run_restic_command(cmd_args)
    except _restic.ResticRunnerError as err:
        raise ResticManagerError(f"[stage:restic-cmd] {err}") from err


def push_restic_repo_to_pcloud() -> None:
    """Trigger post-backup sync of the restic repo to pCloud.

    Exposed here for explicit invocation by higher-level workflows.
    """
    try:
        _restic.push_restic_repo_to_pcloud()
    except _restic.ResticRunnerError as err:
        raise ResticManagerError(f"[stage:restic-push] {err}") from err


__all__ = [
    "ResticRunnerError",
    "has_restic_repository",
    "initialize_restic_repository",
    "run_backup",
    "run_restic_command",
    "push_restic_repo_to_pcloud",
]
