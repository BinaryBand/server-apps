# Refactor Plan: Ports & Adapters + Ansible Vault Secrets

## Context

The project has good bones (clean Pydantic models, resumable checkpoints, one working port/adapter pair) but structural debt: ~8 pure re-export shims, a `src/toolbox/` directory that mixes infrastructure utilities with dead wrappers, and subprocess calls (restic, docker, ansible, health checks) that have no port abstractions, making them hard to test or swap. The secrets system is a global dotenv singleton with no injection point.

Goals:

1. **Restructure** — eliminate shims, flatten `toolbox/`, give everything a clear home
2. **Add missing ports** — secrets, restic, permissions, health prober
3. **Ansible Vault** — make secrets backend swappable; ship `AnsibleVaultSecretProvider` as the production adapter
4. **Enable import-linter** — uncomment the aspirational contracts once ports are in place

---

## Phase 1: New Directory Structure

### Rename `src/toolbox/` → `src/infra/`

`toolbox` is ambiguous. `infra` clearly means "platform/infrastructure utilities used by adapters and orchestrators."

```text
src/infra/
  runtime.py             # ← toolbox/core/runtime.py (path resolution, repo_root)
  locking.py             # ← toolbox/core/locking.py
  polling.py             # ← toolbox/core/polling.py
  config.py              # ← toolbox/core/config.py (rclone/restic config getters)
  io/
    state_io.py          # ← toolbox/io/state_io.py
    state_helpers.py     # ← toolbox/io/state_helpers.py
  docker/
    compose_cli.py       # ← toolbox/docker/compose_cli.py
    compose_storage.py   # ← toolbox/docker/compose_storage.py
    volumes_config.py    # ← toolbox/docker/volumes_config.py
    volumes_inspector.py # ← toolbox/docker/volumes_inspector.py
    rclone.py            # ← toolbox/docker/wrappers/rclone.py (flatten nested wrapper)
```

### Files to DELETE (pure shims, zero logic)

| File | Reason |
| --- | --- |
| `src/toolbox/docker/health.py` | Re-exports `src/observability/health.py` |
| `src/toolbox/docker/health_utils.py` | Re-exports `src/observability/health_utils.py` |
| `src/toolbox/docker/volumes.py` | Re-exports `src/storage/volumes.py` |
| `src/toolbox/docker/compose.py` | Re-exports `src/storage/compose.py` |
| `src/toolbox/core/ansible/ansible_runner.py` | Re-exports `src/permissions/ansible.py` |
| `src/toolbox/core/ansible/ansible_playbook.py` | Re-exports `src/permissions/ansible.py` |
| `src/toolbox/docker/wrappers/restic/restic_api.py` | Re-exports `src/backup/restic.py` |
| `src/toolbox/docker/wrappers/restic/restic_run.py` | Re-exports `src/backup/restic.py` |
| `src/toolbox/backups/restore.py` | Monkeypatch shim — confirmed dead |

After deletion, `src/toolbox/` is gone entirely.

---

## Phase 2: New Ports

Add to `src/ports/`:

### `src/ports/secrets.py` (mirror adrift's pattern exactly)

```python
from typing import Protocol

class SecretProviderPort(Protocol):
    def get(self, key: str, default: str = "") -> str: ...
```

### `src/ports/restic_runner.py`

```python
from typing import Protocol

class ResticRunnerPort(Protocol):
    def ensure_repo(self) -> None: ...
    def run_backup(self, excludes: list[str], target: str) -> None: ...
    def run_restore(self, snapshot: str, target: str) -> None: ...
    def list_snapshots(self) -> list[dict]: ...
    def push_to_remote(self, remote: str) -> None: ...
```

### `src/ports/permissions_runner.py`

```python
from typing import Literal, Protocol

PermissionsMode = Literal["bootstrap", "runtime", "reset"]

class PermissionsRunnerPort(Protocol):
    def run(self, mode: PermissionsMode, *, dry_run: bool = False) -> None: ...
```

### `src/ports/health_prober.py`

```python
from typing import Protocol

class HealthProberPort(Protocol):
    def check_docker(self) -> bool: ...
    def check_containers(self, names: list[str]) -> dict[str, bool]: ...
    def run_all(self) -> None: ...
```

---

## Phase 3: New Adapters

### 3a. Secrets Adapters

**`src/adapters/secrets/env_provider.py`** — replaces current `src/toolbox/core/secrets.py`

```python
import os, sys
from dotenv import find_dotenv, load_dotenv
from src.ports.secrets import SecretProviderPort

class EnvironmentSecretProvider(SecretProviderPort):
    def __init__(self) -> None:
        if "PYTEST_CURRENT_TEST" not in os.environ and "pytest" not in sys.modules:
            load_dotenv(find_dotenv())

    def get(self, key: str, default: str = "") -> str:
        return os.getenv(key, default)
```

**`src/adapters/secrets/vault_provider.py`** — new Ansible Vault backend

```python
import os, yaml
from pathlib import Path
from ansible.parsing.vault import VaultLib, VaultSecret
from ansible.constants import DEFAULT_VAULT_ID_MATCH
from src.ports.secrets import SecretProviderPort

class AnsibleVaultSecretProvider(SecretProviderPort):
    """Reads secrets from an ansible-vault encrypted YAML file.

    Vault password source priority:
      1. password_file kwarg  (path to a plaintext file)
      2. password kwarg       (inline string, less secure)
    Vault data file: ansible/vault.yml (encrypted YAML key→value mapping).
    """

    def __init__(
        self,
        vault_file: Path,
        *,
        password_file: str | None = None,
        password: str | None = None,
    ) -> None:
        pw = self._load_password(password_file, password)
        vault_secret = VaultSecret(pw.encode())
        vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, vault_secret)])
        decrypted = vault.decrypt(vault_file.read_bytes())
        self._data: dict[str, str] = yaml.safe_load(decrypted) or {}

    @staticmethod
    def _load_password(password_file: str | None, password: str | None) -> str:
        if password_file:
            return Path(password_file).read_text().strip()
        if password:
            return password
        raise RuntimeError(
            "Ansible Vault requires VAULT_PASSWORD_FILE or VAULT_PASSWORD"
        )

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)
```

**Wiring — `src/infra/secrets.py`** (replaces `src/toolbox/core/secrets.py`):

```python
# All existing callers (config.py, runtime.py) keep calling read_secret() unchanged.
# Backend is auto-detected from env vars; swappable in tests via set_secret_provider().
import os
from src.ports.secrets import SecretProviderPort

_provider: SecretProviderPort | None = None

def _auto_detect() -> SecretProviderPort:
    vault_file = os.getenv("VAULT_FILE")
    if vault_file:
        from src.adapters.secrets.vault_provider import AnsibleVaultSecretProvider
        from src.infra.runtime import repo_root
        return AnsibleVaultSecretProvider(
            repo_root() / vault_file,
            password_file=os.getenv("VAULT_PASSWORD_FILE"),
            password=os.getenv("VAULT_PASSWORD"),
        )
    from src.adapters.secrets.env_provider import EnvironmentSecretProvider
    return EnvironmentSecretProvider()

def set_secret_provider(provider: SecretProviderPort) -> None:
    global _provider
    _provider = provider

def read_secret(name: str, default: str | None = None) -> str | None:
    global _provider
    if _provider is None:
        _provider = _auto_detect()
    result = _provider.get(name, "")
    return result or default

secret = read_secret  # backwards-compatible alias
```

No changes needed to `src/infra/config.py` or `src/infra/runtime.py` — they keep calling `read_secret()`.

### 3b. Restic Adapter

**`src/adapters/restic/docker_restic.py`** — move logic from `src/backup/restic.py`:

- `DockerResticAdapter(ResticRunnerPort)` wraps all current subprocess calls
- `src/backup/restic.py` becomes a thin shim delegating to `DockerResticAdapter` (preserves import paths during migration)

### 3c. Permissions Adapter

**`src/adapters/permissions/ansible_adapter.py`** — move logic from `src/permissions/ansible.py`:

- `AnsiblePermissionsAdapter(PermissionsRunnerPort)` wraps current subprocess logic
- `src/permissions/ansible.py` kept as a thin backwards-compat shim

### 3d. Health Adapter

**`src/adapters/health/docker_health.py`** — extract subprocess calls from `src/observability/health.py`:

- `DockerHealthAdapter(HealthProberPort)`
- `src/observability/health.py` updated to delegate to the adapter

---

## Phase 4: Ansible Vault Setup

### New file: `ansible/vault.yml`

Created (not committed to git) by running:

```bash
ansible-vault create ansible/vault.yml
```

Contains all secrets currently in `.env`:

```yaml
# ansible/vault.yml — ansible-vault encrypted at rest
MINIO_ROOT_USER: "..."
MINIO_ROOT_PASSWORD: "..."
PCLOUD_ACCESS_TOKEN: "..."
RCLONE_REMOTE: "pcloud"
RESTIC_PCLOUD_REMOTE: "pcloud:Backups/Restic"
```

### `.gitignore` additions

```text
.vault-password
ansible/vault.yml
```

Keep `.env` in `.gitignore` as well during the migration period.

### Runtime env vars for vault mode

```bash
export VAULT_FILE=ansible/vault.yml
export VAULT_PASSWORD_FILE=.vault-password   # or VAULT_PASSWORD=...
```

### `ansible/group_vars/all.yml` update

```yaml
vault_file: "{{ playbook_dir }}/../ansible/vault.yml"
```

Reference secrets in playbooks via `ansible-vault` decryption rather than `lookup('ansible.builtin.env', ...)`.

---

## Phase 5: Enable Import-Linter

Once ports are in place, uncomment the aspirational contract in `pyproject.toml`:

```toml
[[tool.importlinter.contracts]]
name = "App Services must not import Infrastructure concrete modules"
type = "forbidden"
source_modules = ["src.workflows", "src.orchestrators"]
forbidden_modules = [
    "src.infra.docker.compose",
    "src.infra.docker.health",
    "src.adapters",
]
```

---

## Summary of Changes

### Files moved (rename + update imports)

| Old path | New path |
| --- | --- |
| `src/toolbox/core/runtime.py` | `src/infra/runtime.py` |
| `src/toolbox/core/locking.py` | `src/infra/locking.py` |
| `src/toolbox/core/polling.py` | `src/infra/polling.py` |
| `src/toolbox/core/config.py` | `src/infra/config.py` |
| `src/toolbox/core/secrets.py` | `src/infra/secrets.py` (+ port wiring) |
| `src/toolbox/io/state_io.py` | `src/infra/io/state_io.py` |
| `src/toolbox/io/state_helpers.py` | `src/infra/io/state_helpers.py` |
| `src/toolbox/docker/compose_cli.py` | `src/infra/docker/compose_cli.py` |
| `src/toolbox/docker/compose_storage.py` | `src/infra/docker/compose_storage.py` |
| `src/toolbox/docker/volumes_config.py` | `src/infra/docker/volumes_config.py` |
| `src/toolbox/docker/volumes_inspector.py` | `src/infra/docker/volumes_inspector.py` |
| `src/toolbox/docker/wrappers/rclone.py` | `src/infra/docker/rclone.py` (flatten) |

### Files deleted

`src/toolbox/docker/{health,health_utils,volumes,compose}.py`, `src/toolbox/core/ansible/`, `src/toolbox/docker/wrappers/restic/`, `src/toolbox/backups/restore.py`

### New files

| File | Purpose |
| --- | --- |
| `src/ports/secrets.py` | `SecretProviderPort` protocol |
| `src/ports/restic_runner.py` | `ResticRunnerPort` protocol |
| `src/ports/permissions_runner.py` | `PermissionsRunnerPort` protocol |
| `src/ports/health_prober.py` | `HealthProberPort` protocol |
| `src/adapters/secrets/env_provider.py` | dotenv adapter |
| `src/adapters/secrets/vault_provider.py` | Ansible Vault adapter |
| `src/adapters/restic/docker_restic.py` | docker-compose restic adapter |
| `src/adapters/permissions/ansible_adapter.py` | ansible-playbook adapter |
| `src/adapters/health/docker_health.py` | docker health probe adapter |
| `ansible/vault.yml` | encrypted secrets (not in git) |

### Modified files

| File | Change |
| --- | --- |
| `src/infra/secrets.py` | Port-backed `read_secret()` with auto-detect |
| `pyproject.toml` | Uncomment import-linter contracts; update module paths |
| `src/workflows/pipeline.py` | Update imports to `src.infra.*` |
| All orchestrators | Update imports to `src.infra.*` |
| `.gitignore` | Add `.vault-password`, `ansible/vault.yml` |

---

## Suggested Execution Order

1. Move + rename `src/toolbox/` → `src/infra/` (mass find-and-replace on imports)
2. Delete shim files
3. Add `src/ports/secrets.py` + both secret adapters + wire `src/infra/secrets.py`
4. Verify all tests pass; create `ansible/vault.yml`
5. Add remaining ports (`restic_runner`, `permissions_runner`, `health_prober`)
6. Move adapter logic (`docker_restic`, `ansible_adapter`, `docker_health`)
7. Update orchestrators to use ports where possible
8. Enable import-linter contracts

---

## Verification

1. `python -m pytest tests/` — all tests pass throughout each phase
2. `PYTHONPATH=. .venv/bin/lint-imports` — import contracts pass after Phase 5
3. `ruff check src/` — clean after each phase
4. Vault smoke test:
   ```bash
   VAULT_FILE=ansible/vault.yml VAULT_PASSWORD_FILE=.vault-password \
     python -c "from src.infra.secrets import read_secret; print(read_secret('MINIO_ROOT_USER'))"
   ```
5. Run `python runbook/backup.py` against a test environment end-to-end
