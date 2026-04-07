from __future__ import annotations

from src.toolbox.docker.compose_storage import (
    external_alias_name_pairs,
    rendered_compose_config,
    service_volume_sources,
)

import subprocess


def _list_docker_volumes(*args: str) -> list[str]:
    cmd: list[str] = ["docker", "volume", "ls", *args, "--format", "{{.Name}}"]
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        cmd, check=False, capture_output=True, text=True
    )
    if proc.returncode != 0:
        return []
    return list(filter(None, map(str.strip, proc.stdout.splitlines())))


def _fallback_configured_volumes() -> set[str]:
    """Return configured volume names from compose config and external aliases."""
    configured: set[str] = set(external_alias_name_pairs().values())

    compose_volumes = rendered_compose_config().get("volumes", {})
    for raw_cfg in compose_volumes.values():
        volume_name = raw_cfg.get("name", "")
        if volume_name:
            configured.add(volume_name)

    return configured


def list_project_volumes(project: str) -> list[str]:
    """List compose-managed volumes for this stack."""
    volumes: list[str] = _list_docker_volumes(
        "--filter", f"label=com.docker.compose.project={project}"
    )
    if volumes:
        return volumes

    configured = _fallback_configured_volumes()
    existing = set(_list_docker_volumes())
    return sorted(name for name in configured if name in existing)


def remove_project_volumes(project: str, *, dry_run: bool = False) -> tuple[int, int]:
    """Remove project volumes and return `(removed, failed)` counters."""
    volumes = list_project_volumes(project)
    if not volumes:
        print("No project volumes found.")
        return 0, 0

    removed = 0
    for volume in volumes:
        if dry_run:
            print(f"Would remove volume: {volume}")
            removed += 1
            continue

        try:
            subprocess.run(["docker", "volume", "rm", "-f", volume], check=True)
            removed += 1
        except subprocess.CalledProcessError:
            print(f"Failed to remove volume: {volume}")

    return (removed, len(volumes) - removed)
