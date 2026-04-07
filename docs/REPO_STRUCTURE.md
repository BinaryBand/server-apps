# Repository Structure

Centralized ownership and navigation map for project scaffolding.

## Infrastructure Boundary

### ansible/

- Authority for host permissions and runtime reconciliation.
- Primary entry points:
  - `apply-permissions.yml` for runtime/bootstrap/reset modes.
  - `playbooks/provision.yml` for provisioning flows.
  - `tasks/reconcile-startup.yml` for shared startup reconciliation.
- Core data:
  - `permissions.yml`
  - `group_vars/all.yml`
  - `manifests/*.yml`

### compose/

- Container topology and service runtime definitions.
- Files:
  - `base.yml`: canonical service definitions.
  - `dev.yml`: local/development overrides.
- Default host paths (via env fallback):
  - media: `${MEDIA_MOUNT_DIR:-./runtime/media}`
  - logs: `${LOGS_DIR:-./runtime/logs}`
  - minio: `${MINIO_DATA_DIR:-./minio}`

### configs/

- Static service configuration assets used by compose or workflows.
- Current files:
  - `backup-include.txt`
  - `baikal-apache.conf`

## Runtime Boundary

### runtime/

Generated operational state used during workflow execution.

- `checkpoints/`: idempotent workflow checkpoint state.
- `locks/`: inter-workflow lock files.
- `state/`: reconciler state snapshots.
- `media/`: default media mount root.

Path resolution defaults are implemented in `src/toolbox/core/runtime.py` and can be overridden with environment variables such as `STATE_DIR`, `CHECKPOINTS_DIR`, `LOCKS_DIR`, `MEDIA_DATA_PATH`, and `LOGS_DIR`.

## Python Domain Boundaries

- `src/workflows/`: workflow checkpoint and stage execution layer.
- `src/orchestrators/`: command-level orchestration entrypoints.
- `src/reconciler/`: reconciliation domain and adapters.
- `src/toolbox/`: infrastructure adapters pending further concern-based breakup.
