Refactor plan: split `src/toolbox/docker/health.py` and `src/toolbox/docker/volumes.py`
==========================================================================

Goal
----
Split large modules into smaller, focused modules while preserving public API.

Principles
----------
- Keep top-level function names exported from the original modules so callers remain unchanged.
- Extract implementation helpers into new modules and import them back in the original file.
- Add unit tests for extracted helpers where possible.

Suggested split (exact diffs below)
-----------------------------------

1) health.py -> create `src/toolbox/docker/health_utils.py`
   - Move internal helpers into `health_utils.py`:
     - `_run_command`, `_default_command_detail`, `_format_command_failure`,
       `_create_command_probe`, `_run_wait_loop`, `_raise_command_failure`,
       `_require_last_result`
   - Keep public API in `health.py` and import the moved helpers.

2) volumes.py -> create `src/toolbox/docker/volumes_inspector.py` and `src/toolbox/docker/volumes_config.py`
   - `volumes_inspector.py`: `_list_docker_volumes`, `probe_external_volume`,
     `list_project_volumes`, `remove_project_volumes`
   - `volumes_config.py`: `logical_volume_names`, `_resolve_volume_source`,
     `_logical_source`, `_storage_source`, `required_external_volume_names`,
     `host_bind_path`, `logical_volume_mount_source`, `storage_mount_source`,
     `storage_docker_mount_flags`, `rclone_docker_volume_flags`
   - Keep `src/toolbox/docker/volumes.py` as the public façade that imports and re-exports names.

Exact diffs (high-level)
------------------------

1) Add `health_utils.py` with the helper functions copied verbatim from `health.py`.

2) Update `health.py` top to `from .health_utils import ( _run_command, _default_command_detail, ... )`
   and remove the moved helper definitions from `health.py`.

3) Add `volumes_inspector.py` and `volumes_config.py` similarly and update
   `volumes.py` to import and re-export the public functions.

Testing and rollout
-------------------
- Run unit tests and linter after making the changes.
- Keep changes in a feature branch and open a PR for review; CI should run `pytest` and `lizard` gate.

Estimated effort: 4-8 hours (including tests and CI verification).
