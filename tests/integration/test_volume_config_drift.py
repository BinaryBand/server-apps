from __future__ import annotations

from pathlib import Path

from src.storage.compose import external_alias_name_pairs, rendered_compose_config
from src.storage.volumes import required_external_volume_names
from src.toolbox.core.runtime import PROJECT_NAME, repo_root


def _collect_external_volume_names(compose_path: Path) -> set[str]:
    names: set[str] = set()
    lines = compose_path.read_text(encoding="utf8").splitlines()

    in_volumes = False
    current_name: str | None = None
    current_external = False
    current_volume_entry = False

    def flush_current() -> None:
        nonlocal current_name, current_external, current_volume_entry
        if current_volume_entry and current_external and current_name:
            names.add(current_name)
        current_name = None
        current_external = False
        current_volume_entry = False

    for raw in lines:
        if not in_volumes:
            if raw.startswith("volumes:"):
                in_volumes = True
            continue

        if raw and not raw.startswith(" "):
            flush_current()
            break

        if raw.startswith("  ") and not raw.startswith("    ") and raw.strip().endswith(":"):
            flush_current()
            current_volume_entry = True
            continue

        if not current_volume_entry:
            continue

        stripped = raw.strip()
        if stripped.startswith("name:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            current_name = value
            continue

        if stripped.startswith("external:"):
            value = stripped.split(":", 1)[1].strip().lower()
            current_external = value == "true"

    flush_current()
    return names


def _collect_external_alias_name_pairs(compose_path: Path) -> dict[str, str]:
    alias_to_name: dict[str, str] = {}
    lines = compose_path.read_text(encoding="utf8").splitlines()

    in_volumes = False
    current_alias: str | None = None
    current_name: str | None = None
    current_external = False
    current_volume_entry = False

    def flush_current() -> None:
        nonlocal current_alias, current_name, current_external, current_volume_entry
        if current_volume_entry and current_external and current_alias and current_name:
            alias_to_name[current_alias] = current_name
        current_alias = None
        current_name = None
        current_external = False
        current_volume_entry = False

    for raw in lines:
        if not in_volumes:
            if raw.startswith("volumes:"):
                in_volumes = True
            continue

        if raw and not raw.startswith(" "):
            flush_current()
            break

        if raw.startswith("  ") and not raw.startswith("    ") and raw.strip().endswith(":"):
            flush_current()
            current_volume_entry = True
            current_alias = raw.strip().removesuffix(":")
            continue

        if not current_volume_entry:
            continue

        stripped = raw.strip()
        if stripped.startswith("name:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            current_name = value
            continue

        if stripped.startswith("external:"):
            value = stripped.split(":", 1)[1].strip().lower()
            current_external = value == "true"

    flush_current()
    return alias_to_name


def test_python_external_volume_list_matches_compose_external_names() -> None:
    root = repo_root()
    compose_files = [root / "compose" / "base.yml", root / "compose" / "dev.yml"]

    compose_external_names: set[str] = set()
    for compose_file in compose_files:
        compose_external_names |= _collect_external_volume_names(compose_file)

    python_external_names = set(required_external_volume_names())
    assert python_external_names == compose_external_names


def test_runtime_project_name_matches_rendered_compose() -> None:
    rendered_name = rendered_compose_config().get("name")
    assert rendered_name == PROJECT_NAME


def test_compose_external_aliases_match_rendered_reader() -> None:
    root = repo_root()
    compose_files = [root / "compose" / "base.yml", root / "compose" / "dev.yml"]

    compose_pairs: dict[str, str] = {}
    for compose_file in compose_files:
        compose_pairs.update(_collect_external_alias_name_pairs(compose_file))

    assert compose_pairs == external_alias_name_pairs()
