# Handoff: backup.py `main()` complexity reduction

## Context

`src/orchestrators/backup.py:main` is flagged by Lizard at CCN 3, NLOC 21.
The CCN comes from two decision points inside the lock block:

- `if restic_pcloud_sync_enabled():` (+1)
- `except Exception` (+1)
- base (+1) = **CCN 3**

The fix is a single extraction. Everything else in this file is already clean.

---

## Step 1 — Extract `_run_restic_push`

Pull the entire try/if block out of `main()` into a new helper:

**Before** (`backup.py:main`, lines 146–154):
```python
        checkpoint.finish(observed="BackupCompleted", ok=True)
        try:
            if restic_pcloud_sync_enabled():
                print("[stage:restic-push] Pushing restic repo to cloud")
                push_restic_to_cloud()
                print("[stage:restic-push] Restic repo pushed to cloud")
        except Exception as err:
            # Don't fail the overall backup if the push step fails — log and continue.
            print(f"[stage:restic-push] Warning: push to cloud failed: {err}")
        print("[stage:complete] Backup pipeline completed")
```

**After** — add this function above `main()`:
```python
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
```

**After** — updated `main()`:
```python
def main() -> None:
    resume_enabled = runbook_resume_enabled()
    root: Path = repo_root()
    config = BackupConfig.from_toml(root / "configs" / "backup.toml")

    with RunbookLock("backup-restore-reset", locks_root()):
        checkpoint = start_checkpoint(
            "backup",
            "BackupCompleted",
            root=checkpoints_root(),
            resume=resume_enabled,
        )
        _run_backup_stages(checkpoint, config)
        checkpoint.finish(observed="BackupCompleted", ok=True)
        _run_restic_push()
        print("[stage:complete] Backup pipeline completed")
```

Expected result: `main` drops to **CCN 1, NLOC ~14**.

---

## Step 2 — Update `docs/COMPLEXITY.md`

In section 8 (Current Violations table), remove the `backup.py:main` row:

```
| src/orchestrators/backup.py | main | 21 | 3 | 0 | 27 |
```

In section 5 (Resolution Log), add an entry:

```markdown
#### src/orchestrators/backup.py:main

- **Before:** NLOC: 21, CCN: 3
- **After:** NLOC: ~14, CCN: 1
- **Refactoring steps:**
  - Extracted restic cloud-push try/if block into `_run_restic_push()`.
  - main() now reads as pure orchestration with no inline decision logic.
  - Validated with Lizard: violation resolved.
```

---

## Step 3 — Minor style fix in `restore.py`

Add a blank line before `_run_stream_restores` at line 84 (missing blank line between functions):

```python
    checkpoint.finish(observed="RestoreCompleted", ok=True)
    print("[stage:complete] Restore pipeline completed")

                                          # ← blank line here
def _run_stream_restores(config: BackupConfig, checkpoint: OperationCheckpoint) -> None:
```

---

## Validation

After all changes, run:

```sh
python -m lizard src/orchestrators/backup.py src/orchestrators/restore.py -C 5 -L 25 -a 4 -w
```

Expected: no warnings from either file.

Also run the test suite to confirm no regressions:

```sh
python -m pytest tests/unit/test_restic_push.py -v
```
