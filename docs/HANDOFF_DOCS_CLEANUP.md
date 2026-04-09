# Handoff: docs/ Cleanup

Current state: 11 files, several stale, two redundant, one ephemeral.
Target state: 8 files — accurate, non-overlapping, no dead references.

---

## Deletions (3 files)

### 1. `docs/REFACTOR_PLAN.md` — DELETE

**Why:** This was the original design doc for the ports & adapters refactor. Phases 1–3 are now partially or fully complete, and all remaining work is already captured in `NEXT_STEPS.md` with better specificity. `REFACTOR_PLAN.md` is now a historical artifact with significant overlap. Keeping it creates confusion about what's done vs. still planned.

### 2. `docs/VSCODE_SETUP.md` — DELETE

**Why:** It's labelled a "template" and references scripts that don't exist:
- `runbook/quality/check_complexity.py` — not in repo
- `runbook/quality/check_dead_code.py` — not in repo

The actual commands are in `.vscode/tasks.json` (e.g. `scripts/quality/lizard_file_gate.py`, `python -m lizard`, `python -m vulture`). `CONTRIBUTING.md` already covers tooling setup correctly. This doc is misleading rather than helpful.

### 3. `docs/HANDOFF_BACKUP_REFACTOR.md` — DELETE (after merging into NEXT_STEPS.md)

**Why:** Ephemeral task handoff. Its content (extract `_run_restic_push` from `backup.py:main`) should live in `NEXT_STEPS.md` as a pending step, then this file should be removed.

---

## Updates (5 files)

### 4. `docs/NEXT_STEPS.md` — prepend Step 0

Merge in the content from `HANDOFF_BACKUP_REFACTOR.md` as a new **Step 0** before the existing steps. The extract-to-`_run_restic_push` task is independent of and smaller than the `src/toolbox/` migration, so it should be done first.

Add this block at the top, after the "Current State" section:

```markdown
## Step 0 — Reduce `backup.py:main` complexity (Lizard CCN 3)

Extract the restic cloud-push try/if block into `_run_restic_push()`:

**New function** (add above `main()`):
    def _run_restic_push() -> None:
        """Optionally push the restic repo offsite. Gated by RESTIC_PCLOUD_SYNC.
        Failure is non-fatal — logged and swallowed so the backup result stands."""
        try:
            if restic_pcloud_sync_enabled():
                print("[stage:restic-push] Pushing restic repo to cloud")
                push_restic_to_cloud()
                print("[stage:restic-push] Restic repo pushed to cloud")
        except Exception as err:
            print(f"[stage:restic-push] Warning: push to cloud failed: {err}")

**Updated `main()`** — replace the try/if block with:
        _run_restic_push()
        print("[stage:complete] Backup pipeline completed")

Also:
- Add missing blank line before `_run_stream_restores` in `restore.py` (line 84).
- Update `docs/COMPLEXITY.md` section 8: remove the `backup.py:main` row and add a resolution log entry.

Validate: `python -m lizard src/orchestrators/backup.py -C 5 -L 25 -a 4 -w` → no warnings.
```

Then renumber the existing Steps 1–6 to Steps 1–6 (they stay the same, just the new block is prepended).

---

### 5. `docs/BACKUP_PIPELINE.md` — remove compress, fix file table

**a) Remove `[[compress]]` from the TOML config example.**

The `[[compress]]` section currently appears in the config example starting at line 85. It was removed from the codebase. Delete that TOML block entirely. Update the preamble "Three strategy sections:" to "Two strategy sections:".

**b) Fix orchestrator descriptions** (lines 126–134):

Change:
```
Runs stages in order: gather → restic → stream × N → compress × N.
```
To:
```
Runs stages in order: gather → restic → stream × N.
```

Change:
```
Runs stages in order: restic restore → stream × N (reversed) → compress × N (reversed).
```
To:
```
Runs stages in order: restic restore → stream × N (reversed).
```

**c) Fix the file table** (lines 139–150):

Remove the two rows for deleted files:
- `src/ports/object_sync.py` — "Deleted — replaced by `backup_stage.py`" (row is fine to keep as a note, or just remove it)
- `src/adapters/rclone/compress_stage.py` — "(removed)"
- `src/backup/stream_sync.py` — "Deleted — absorbed into `stage_runner.py`"

Keep only rows for files that currently exist.

**d) Policy notes** (lines 97–120):

The "High-file-count buckets" policy note says "prefer a `[[compress]]` entry". Compress is gone. Replace that recommendation with: prefer a dedicated `[[stream]]` block targeting a pre-zipped or pre-aggregated destination, or accept higher transfer counts. Alternatively, remove this note entirely if it's no longer actionable.

---

### 6. `docs/FLOW.md` — update stale toolbox links

All references to `src/toolbox/core/config.py`, `src/toolbox/core/locking.py`, `src/toolbox/core/polling.py`, and `src/toolbox/core/secrets.py` in the markdown text and mermaid diagram need to be updated.

**Migration is in progress** — `src/toolbox/` files are being moved to `src/infra/` (see `NEXT_STEPS.md`). Two options; pick one:

**Option A (simpler):** Add a single note at the top of the file:
```markdown
> ⚠️ **Migration in progress** — links to `src/toolbox/core/*` will move to `src/infra/*`
> once the migration in `NEXT_STEPS.md` is complete.
```

**Option B (more accurate):** Update all links now to point to `src/infra/*`:
- `src/toolbox/core/config.py` → `src/infra/config.py`
- `src/toolbox/core/locking.py` → `src/infra/locking.py`
- `src/toolbox/core/polling.py` → `src/infra/polling.py`
- `src/toolbox/core/secrets.py` → `src/infra/secrets.py`
- `src/toolbox/docker/compose_storage.py` → `src/infra/docker/compose_storage.py`

Option A is the safer handoff choice given the migration is incomplete.

---

### 7. `docs/REPO_STRUCTURE.md` — update Python domain section

The `src/toolbox/` entry currently says:
```
src/toolbox/: implementation backend retained for compatibility during migration.
```

Replace with entries for the new structure:

```markdown
- `src/infra/`: platform utilities (runtime paths, locking, polling, config, docker wrappers). Used by adapters and orchestrators — not imported by domain or workflow layers directly.
- `src/adapters/`: concrete implementations of ports (rclone, restic, secrets, permissions, health). One subdirectory per domain.
- `src/ports/`: port protocols (`BackupStage`, `SecretProviderPort`, `ResticRunnerPort`, etc.).
- `src/toolbox/`: **being removed** — contents migrated to `src/infra/`. See `NEXT_STEPS.md`.
```

Also check whether `configs/` description is still accurate (it currently says `backup-include.txt` and `baikal-apache.conf` — verify these still exist before updating).

---

### 8. `docs/COMPLEXITY.md` — update section 8 violations table

Section 8 lists violations captured before the agent's refactoring pass. Several are now resolved. After Step 0 above is complete (`_run_restic_push` extraction), the following violations will be resolved and their rows should be removed from the table:

| Was in table | Status after current fixes |
|---|---|
| `src/permissions/ansible.py:run_permissions_playbook` | ✅ Resolved (extracted `_handle_playbook_error`) |
| `src/orchestrators/backup.py:_run_backup_stages` | ✅ Resolved (extracted `_run_gather_stage`, `_run_backup_streams`) |
| `src/orchestrators/backup.py:main` | ✅ Resolved after Step 0 (`_run_restic_push` extraction) |
| `src/orchestrators/restore.py:_run_restore` | ✅ Resolved (extracted `_run_stream_restores`) |
| `src/toolbox/core/locking.py:_is_stale` | ✅ Resolved (extracted `_read_marker`, `_extract_pid`, `_check_pid_stale`) |

Remaining (verify with `python -m lizard src runbook -C 5 -L 25 -a 4 -w` after Step 0):

| File | Function | Likely status |
|---|---|---|
| `src/backup/restic.py:has_restic_repo` | Listed at NLOC 19, CCN 1 — may be below threshold; re-verify |
| `src/toolbox/docker/wrappers/rclone.py:rclone_copy` | Listed at NLOC 25, CCN 2 — at threshold; re-verify |
| `src/toolbox/docker/wrappers/rclone.py:rclone_lsf` | Listed at NLOC 25, CCN 4 — at threshold; re-verify |

Add resolution log entries for the 5 resolved violations (see section 5 format).

---

## Files to leave unchanged

- `docs/ARCHITECTURE.md` — accurate, well-structured
- `docs/CONTRIBUTING.md` — accurate, well-structured

---

## Execution order

1. Merge `HANDOFF_BACKUP_REFACTOR.md` content into `NEXT_STEPS.md` (Step 0 block)
2. Delete `REFACTOR_PLAN.md`, `VSCODE_SETUP.md`, `HANDOFF_BACKUP_REFACTOR.md`
3. Update `BACKUP_PIPELINE.md` (compress removal)
4. Update `REPO_STRUCTURE.md` (add infra/adapters/ports entries)
5. Update `FLOW.md` (migration note or link update)
6. Update `COMPLEXITY.md` section 8 (re-run Lizard first to get current counts)

Steps 3–6 are independent and can be done in any order or in parallel.

---

## Post-cleanup state

| File | Purpose |
|---|---|
| `ARCHITECTURE.md` | Design rules, module map, layer contracts |
| `CONTRIBUTING.md` | Setup, tooling config, contribution rules |
| `BACKUP_PIPELINE.md` | Backup port/adapter design, config reference |
| `FLOW.md` | start.py call graph and mermaid diagram |
| `REPO_STRUCTURE.md` | Filesystem and Python domain map |
| `COMPLEXITY.md` | Lizard protocol, violation log, current violations |
| `NEXT_STEPS.md` | Active migration handoff (toolbox → infra) |
