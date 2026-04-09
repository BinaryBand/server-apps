# Next Steps: Refactor Handoff

See [REFACTOR_PLAN.md](REFACTOR_PLAN.md) for full context and design rationale.

---

## Current State

Phases 1–3 are partially complete:

- ✅ Shim files deleted (`src/toolbox/docker/{health,health_utils,volumes,compose}.py`, `src/toolbox/core/ansible/`, `src/toolbox/docker/wrappers/restic/`, `src/toolbox/backups/restore.py`)
- ✅ New ports created (`src/ports/secrets.py`, `restic_runner.py`, `permissions_runner.py`, `health_prober.py`)
- ✅ Secrets adapters fully implemented (`src/adapters/secrets/env_provider.py`, `vault_provider.py`)
- ✅ `src/infra/secrets.py` wired with auto-detect and `set_secret_provider()`
- ⚠️ `src/infra/` stubs created but **not yet populated** — all files except `secrets.py` are 1-line comments
- ⚠️ `src/toolbox/` still holds all real implementation; nothing imports from `src.infra.*` yet
- ⚠️ Three adapter stubs are empty TODOs (`docker_restic.py`, `ansible_adapter.py`, `docker_health.py`)
- ❌ Import-linter contract is broken (see fix below)

---

## Step 1 — Fix the import-linter contract

The contract added to `pyproject.toml` forbids `src.orchestrators` from importing `src.adapters`, but `backup.py` and `restore.py` already import `RcloneStreamSync` from `src.adapters` — which is intentional and correct. Narrow the forbidden list to `src.infra` only:

```toml
# pyproject.toml
[[tool.importlinter.contracts]]
name = "App Services must not import Infrastructure concrete modules"
type = "forbidden"
source_modules = ["src.workflows", "src.orchestrators"]
forbidden_modules = ["src.infra"]
```

Verify: `PYTHONPATH=. .venv/bin/lint-imports`

---

## Step 2 — Populate `src/infra/` stubs

Each file under `src/infra/` (except `secrets.py`) contains a placeholder comment and needs to be replaced with the real content from its `src/toolbox/` counterpart:

| Stub | Copy from |
| --- | --- |
| `src/infra/config.py` | `src/toolbox/core/config.py` |
| `src/infra/runtime.py` | `src/toolbox/core/runtime.py` |
| `src/infra/locking.py` | `src/toolbox/core/locking.py` |
| `src/infra/polling.py` | `src/toolbox/core/polling.py` |
| `src/infra/io/state_io.py` | `src/toolbox/io/state_io.py` |
| `src/infra/io/state_helpers.py` | `src/toolbox/io/state_helpers.py` |
| `src/infra/docker/compose_cli.py` | `src/toolbox/docker/compose_cli.py` |
| `src/infra/docker/compose_storage.py` | `src/toolbox/docker/compose_storage.py` |
| `src/infra/docker/volumes_config.py` | `src/toolbox/docker/volumes_config.py` |
| `src/infra/docker/volumes_inspector.py` | `src/toolbox/docker/volumes_inspector.py` |
| `src/infra/docker/rclone.py` | `src/toolbox/docker/wrappers/rclone.py` |

Update internal imports within each copied file from `src.toolbox.*` → `src.infra.*`.

---

## Step 3 — Migrate all call-site imports

Every file outside `src/toolbox/` that imports from `src.toolbox.*` needs updating. Current list (from `grep -r "from src.toolbox" src/ --include="*.py"`):

| File | Change |
| --- | --- |
| `src/workflows/checkpoint.py` | `src.toolbox.io.*` → `src.infra.io.*` |
| `src/orchestrators/*.py` | `src.toolbox.core.*` → `src.infra.*` |
| `src/backup/gather.py` | `src.toolbox.docker.wrappers.rclone` → `src.infra.docker.rclone` |
| `src/backup/restore.py` | `src.toolbox.core.*`, `src.toolbox.docker.*` → `src.infra.*` |
| `src/backup/restic.py` | `src.toolbox.core.*`, `src.toolbox.docker.*` → `src.infra.*` |
| `src/reconciler/*.py` | `src.toolbox.core.*`, `src.toolbox.io.*` → `src.infra.*` |
| `src/adapters/rclone/stream_sync.py` | `src.toolbox.core.*`, `src.toolbox.docker.*` → `src.infra.*` |
| `src/storage/compose.py` | `src.toolbox.docker.*` → `src.infra.docker.*` |
| `src/storage/volumes.py` | `src.toolbox.docker.*` → `src.infra.docker.*` |
| `src/observability/health.py` | `src.toolbox.core.*` → `src.infra.*` |
| `src/observability/health_utils.py` | `src.toolbox.core.*` → `src.infra.*` |

After this step: `python -m pytest tests/unit -x` must pass.

---

## Step 4 — Delete `src/toolbox/`

Once all imports are migrated and tests pass, remove the old directory entirely:

```bash
rm -rf src/toolbox/
```

Also delete the one remaining shim that was missed in the earlier pass:

```bash
rm src/toolbox/docker/post_start/jellyfin.py  # already gone after rm -rf above
```

`src/observability/post_start.py` is the canonical home — no replacement needed.

Verify: `python -m pytest tests/ -x` and `PYTHONPATH=. .venv/bin/lint-imports`

---

## Step 5 — Implement the three adapter stubs

### `src/adapters/restic/docker_restic.py`

Move subprocess logic out of `src/backup/restic.py` into `DockerResticAdapter(ResticRunnerPort)`. Leave `src/backup/restic.py` as a thin shim that instantiates and delegates to the adapter (preserves existing import paths).

Key methods to implement: `ensure_repo()`, `run_backup()`, `run_restore()`, `list_snapshots()`, `push_to_remote()`.

### `src/adapters/permissions/ansible_adapter.py`

Move subprocess logic out of `src/permissions/ansible.py` into `AnsiblePermissionsAdapter(PermissionsRunnerPort)`. Keep `src/permissions/ansible.py` as a thin shim.

Key method: `run(mode, *, dry_run)` — wraps the existing `_build_playbook_command` / `_run_or_escalate` logic.

### `src/adapters/health/docker_health.py`

Extract direct subprocess calls from `src/observability/health.py` into `DockerHealthAdapter(HealthProberPort)`. Update `src/observability/health.py` to delegate to the adapter.

Key methods: `check_docker()`, `check_containers()`, `run_all()`.

---

## Step 6 — Ansible Vault setup (manual, on the target host)

```bash
# Create vault file (prompted for password)
ansible-vault create ansible/vault.yml

# Store vault password in a local file (never commit this)
echo "your-vault-password" > .vault-password
chmod 600 .vault-password
```

The vault file should contain the same keys currently in `.env`:

```yaml
MINIO_ROOT_USER: "..."
MINIO_ROOT_PASSWORD: "..."
PCLOUD_ACCESS_TOKEN: "..."
RCLONE_REMOTE: "pcloud"
RESTIC_PCLOUD_REMOTE: "pcloud:Backups/Restic"
# ... all other secrets currently in .env
```

To use vault mode at runtime:

```bash
export VAULT_FILE=ansible/vault.yml
export VAULT_PASSWORD_FILE=.vault-password
python runbook/backup.py
```

Smoke test:

```bash
VAULT_FILE=ansible/vault.yml VAULT_PASSWORD_FILE=.vault-password \
  python -c "from src.infra.secrets import read_secret; print(read_secret('MINIO_ROOT_USER'))"
```

---

## Final Verification Checklist

- [ ] `PYTHONPATH=. .venv/bin/lint-imports` — both contracts kept
- [ ] `python -m pytest tests/unit -x` — all pass
- [ ] `ruff check src/` — clean
- [ ] `python -m vulture src --min-confidence 80` — no dead code in new files
- [ ] `python runbook/backup.py` — end-to-end run succeeds
- [ ] Vault smoke test passes (see Step 6)
