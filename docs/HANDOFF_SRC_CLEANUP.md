# Handoff: src/ Scaffold Cleanup

## Current state summary

83 Python files across 26 directories. Key structural issues:
- ~6 stale shim directories in `src/toolbox/` that should have been deleted in the last refactor pass
- `src/ports/` is 5 micro-files (5–12 lines each) instead of one readable contracts file
- `src/infra/config.py` exists as a **duplicate** of `src/toolbox/core/config.py` — two live implementations of the same module
- Several dead private utilities in `src/observability/health_utils.py` (needs verification)

Nothing here requires Ansible offloading — the Python/Ansible boundary is already correct (Ansible owns permissions/ownership; Python owns runtime sequencing).

---

## A. Delete stale toolbox shim directories

These were supposed to be deleted in the previous refactor pass (marked ✅ in `NEXT_STEPS.md`) but the files are still present. Verify no callers exist, then delete.

### A1. `src/toolbox/core/ansible/`

Single file: `__init__.py` (6 lines). Re-exports `run_permissions_playbook` from `src/permissions/ansible.py`.

**Verify:** `grep -r "from src.toolbox.core.ansible" src/ tests/` → should return nothing.

**Delete:** `rm -rf src/toolbox/core/ansible/`

---

### A2. `src/toolbox/docker/wrappers/restic/`

Single file: `__init__.py` (23 lines). Re-exports everything from `src/backup/restic.py`.

**Verify:** `grep -r "from src.toolbox.docker.wrappers.restic" src/ tests/` → should return nothing.

**Delete:** `rm -rf src/toolbox/docker/wrappers/restic/`

---

### A3. `src/toolbox/backups/`

Empty directory. `__init__.py` is 0 lines. No purpose.

**Delete:** `rm -rf src/toolbox/backups/`

---

### A4. `src/toolbox/docker/post_start/`

Two files: `__init__.py` (9 lines) + `jellyfin.py` (6 lines). The canonical home is already `src/observability/post_start.py`. This directory is a leftover.

**Verify:** `grep -r "from src.toolbox.docker.post_start" src/ tests/` → should return nothing.

**Delete:** `rm -rf src/toolbox/docker/post_start/`

---

### A5. Empty adapter `__init__.py` files

These serve no purpose — all adapter imports go directly to sub-modules.

| File | Lines |
|---|---|
| `src/adapters/__init__.py` | 0 |
| `src/adapters/rclone/__init__.py` | 0 |

**Verify:** `grep -r "from src.adapters import\b" src/ tests/` → should return nothing.

**Delete both files.**

---

## B. Consolidate `src/ports/` into one file

Currently 5 protocol files (5–12 lines each) plus a partial `__init__.py`. Reading the contracts layer means opening 5 files. All 5 protocols fit comfortably in ~50 lines.

### Current layout

```
src/ports/
  __init__.py           (3 lines — only re-exports BackupStage)
  backup_stage.py       (12 lines)
  health_prober.py      (7 lines)
  permissions_runner.py (7 lines)
  restic_runner.py      (9 lines)
  secrets.py            (5 lines)
```

### Target layout

```
src/ports/
  __init__.py           (~50 lines — all 5 protocols)
```

### Steps

1. Move all protocol class definitions into `src/ports/__init__.py`.
2. Delete the 5 individual files.
3. Update all call-site imports:
   - `from src.ports.secrets import SecretProviderPort` → `from src.ports import SecretProviderPort`
   - `from src.ports.backup_stage import BackupStage` → `from src.ports import BackupStage`
   - `from src.ports.restic_runner import ResticRunnerPort` → `from src.ports import ResticRunnerPort`
   - `from src.ports.permissions_runner import PermissionsRunnerPort` → `from src.ports import PermissionsRunnerPort`
   - `from src.ports.health_prober import HealthProberPort` → `from src.ports import HealthProberPort`

**Grep to find all call sites before editing:**
```sh
grep -r "from src.ports\." src/ tests/
```

**Validate:** `python -m pytest tests/unit -x` must pass after the merge.

---

## C. Resolve the `src/infra/config.py` duplicate

`src/infra/config.py` (82 lines) and `src/toolbox/core/config.py` (94 lines) are two live implementations of the same module. This happened because the migration agent wrote real content into `infra/config.py` instead of leaving it as a stub.

**Context:** `NEXT_STEPS.md` Step 2 plans to populate `src/infra/` stubs by copying content from `src/toolbox/`. For `config.py` specifically, the right approach is:

1. **Diff the two files.** The `infra/config.py` version has cleaner error handling (`except ImportError` not `except Exception`, added `_RCLONE_CFG_LOADED` sentinel, print-on-failure). These improvements should be the canonical version.
2. **Replace `toolbox/core/config.py` content with the `infra/config.py` content** — or just declare `infra/config.py` canonical and make `toolbox/core/config.py` a shim pointing to it.
3. **Do not leave both live.** Until the full toolbox→infra import migration (NEXT_STEPS Step 3) is done, the safest path is: keep `toolbox/core/config.py` as the single implementation with the `infra/config.py` improvements merged in, and make `infra/config.py` a one-line re-export:
   ```python
   # src/infra/config.py — transitional shim; will become canonical after migration
   from src.toolbox.core.config import *  # noqa: F401, F403
   ```
   This prevents both files from drifting and gives one source of truth until Step 3 is complete.

---

## D. Verify and remove dead utilities in `health_utils.py`

`src/observability/health_utils.py` contains private helper functions that may be dead. Verify each with grep before removing.

```sh
grep -rn "_create_command_probe\|_run_wait_loop\|_raise_command_failure\|_require_last_result" src/ tests/
```

If any function has **zero callers outside its own file** and **zero callers within health_utils.py**, delete it.

If all four are dead, `health_utils.py` may shrink enough to inline into `health.py` — but only if the combined file stays within Lizard's 25-line function limit (functions within it, not file length). More likely: remove the dead functions and leave `health_utils.py` in place with the remaining used helpers.

**Note:** Do not merge `health_utils.py` into `health.py` blindly — `health.py` is already 328 lines. Function-level length is what Lizard enforces, not file length, but deeply nested helper files reduce readability.

---

## E. Ansible boundary check (conclusion: no changes needed)

**Question:** Can any Python subprocess logic be offloaded to Ansible?

**Assessment:**

| Code | Current owner | Should move? |
|---|---|---|
| `restart_jellyfin()` — `docker restart jellyfin` | Python (`post_start.py`) | No — it's a sequenced pipeline stage with checkpoint resumability, not host config |
| `run_permissions_playbook()` — `ansible-playbook` | Python delegates to Ansible | Already correct — Python orchestrates, Ansible executes permissions |
| Volume removal in `reset.py` | Python → docker subprocess | No — part of reset workflow sequencing |
| Health probes — `docker exec`/`docker inspect` | Python (`health.py`) | No — real-time probes for workflow gating |

The Ansible/Python boundary in `ARCHITECTURE.md` is already correctly drawn. Python owns runtime orchestration and workflow sequencing. Ansible owns host permissions, file ownership, and idempotent system state. No logic should move.

---

## F. Leave unchanged

These are correctly structured — don't touch:

| What | Why |
|---|---|
| `__init__.py` re-export hubs in `backup/`, `storage/`, `workflows/`, `observability/`, `reconciler/` | Intentional public API facades |
| `src/storage/volumes.py` (pure re-export) | Facade isolating callers from toolbox internals; will be updated when toolbox→infra migration completes |
| `src/configuration/` Pydantic models | Correct structure, clean models |
| `src/infra/` stub files (except `config.py`) | Part of NEXT_STEPS.md Step 2 migration — populate, don't delete |
| Adapter TODO stubs (`docker_restic.py`, `ansible_adapter.py`, `docker_health.py`) | Part of NEXT_STEPS.md Step 5 — implement, don't delete |
| `src/toolbox/core/{locking,polling,runtime,secrets,config}.py` | Live implementations until NEXT_STEPS migration completes |

---

## Execution order

Steps A–D are fully independent. Suggested order by impact:

1. **A (toolbox shim deletions)** — run the greps first, then delete; ~10 minutes, pure subtraction
2. **B (ports consolidation)** — mechanical merge + import update; ~20 minutes
3. **C (infra/config.py duplicate)** — requires reading both files and merging improvements; ~15 minutes
4. **D (health_utils dead code)** — grep first, remove if confirmed dead; ~10 minutes

**After each step:** `python -m pytest tests/unit -x` and `ruff check src/`

---

## Post-cleanup file count

| Directory | Before | After |
|---|---|---|
| `src/toolbox/core/ansible/` | 1 file | 0 (deleted) |
| `src/toolbox/docker/wrappers/restic/` | 1 file | 0 (deleted) |
| `src/toolbox/backups/` | 1 file | 0 (deleted) |
| `src/toolbox/docker/post_start/` | 2 files | 0 (deleted) |
| `src/adapters/` empty inits | 2 files | 0 (deleted) |
| `src/ports/` | 6 files | 1 file |
| Net reduction | | **~13 files** |

Remaining `src/` count: ~70 files (down from 83).
