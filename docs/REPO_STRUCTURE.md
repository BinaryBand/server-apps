# Repository Structure

Centralized ownership and navigation map for project scaffolding.

## Infrastructure Boundary

### ansible/

- Authority for host permissions and runtime reconciliation.
- Primary entry points (all under `ansible/playbooks/`):
  - `playbooks/runtime.yml` — runtime/bootstrap/reset permission modes.
  - `playbooks/provision.yml` — provisioning flows.
  - `playbooks/enforce-ssh.yml` — SSH authorized key enforcement.
  - `playbooks/install-timers.yml` — systemd unit enforcement.
- Core data:
  - `permissions.yml`
  - `group_vars/all.yml`
  - `manifests/*.yml`
- See `ansible/README.md` for the full command matrix.

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
  - `backup.toml` — backup strategy configuration (batch + stream).
  - `baikal-apache.conf` — Baikal Apache virtual host config.
  - `rclone.toml` — rclone remote configuration template.

## Runtime Boundary

### runtime/

Generated operational state used during workflow execution.

- `checkpoints/`: idempotent workflow checkpoint state.
- `locks/`: inter-workflow lock files.
- `state/`: workflow state snapshots.
- `media/`: default media mount root.

Path resolution defaults are implemented in `src/infra/` and can be overridden with environment variables such as `STATE_DIR`, `CHECKPOINTS_DIR`, `LOCKS_DIR`, `MEDIA_DATA_PATH`, and `LOGS_DIR`.

## Python Domain Boundaries

- `src/configuration/`: domain models — `WorkflowState`, `BackupConfig`, `StorageManifest`, `ComposeConfig`. No outward dependencies.
- `src/workflows/`: pipeline declaration (`PIPELINE_STEPS`) and stage execution (`workflow_runner`, `checkpoint`).
- `src/orchestrators/`: command-level entrypoints — `start`, `stop`, `backup`, `restore`, `reset`.
- `src/permissions/`: permission execution boundary; delegates host mutation to Ansible playbooks.
- `src/storage/`: compose and volume topology facade used by workflows.
- `src/observability/`: runtime health and probe facade used by workflows.
- `src/backup/`: backup/restore facade for snapshot orchestration and restic bridge.
- `src/infra/`: platform utilities (runtime paths, locking, polling, config, docker wrappers). Used by adapters and orchestrators — not imported by domain or workflow layers directly.
- `src/adapters/`: concrete implementations of ports (rclone, secrets). One subdirectory per domain.
- `src/ports/`: port protocols (`BackupStage`, `SecretProviderPort`).
