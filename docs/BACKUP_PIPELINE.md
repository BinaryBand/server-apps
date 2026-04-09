# Backup Pipeline: Bidirectional BackupStage Port + Compress-Then-Sync Strategy

## Overview

The backup system uses a **ports & adapters** architecture where every backup strategy
implements the `BackupStage` protocol — a bidirectional contract with `backup()` and
`restore()` methods. This makes every strategy fully reversible and swappable.

### Pipeline symmetry

```text
BACKUP:   gather → restic  |  stream (source → cloud)
RESTORE:  restic → volumes |  stream (cloud → source)
```

---

## Port: `BackupStage`

**File:** `src/ports/backup_stage.py`

```python
from typing import Protocol

class BackupStage(Protocol):
    """Port: a reversible backup/restore operation."""
    def backup(self) -> None: ...
    def restore(self) -> None: ...
```

All adapters satisfy this protocol. The orchestrators depend only on this port.

---

## Adapters

### `RcloneStreamSync` — `src/adapters/rclone/stream_sync.py`

Streams files directly between two rclone remotes (or local volume paths) without local staging.

- `backup()`: `rclone sync source → destination`
- `restore()`: `rclone sync destination → source` (direction swapped, excludes preserved)

Runs rclone in a disposable Docker container. Mounts all logical volumes at
`/data/volumes/<name>` and joins the compose network so `minio:9000` is reachable.

<!-- Compress/archive-based staging removed. Use `restic` and `stream` stages only. -->

---

## Stage Runner

**File:** `src/backup/stage_runner.py`

Generic dispatcher for any `BackupStage`:

```python
def run_backup_stage(stage: BackupStage, name: str) -> None: ...
def run_restore_stage(stage: BackupStage, name: str) -> None: ...
```

Replaces the old `stream_sync_stage()` function from `src/backup/stream_sync.py`.

---

## Configuration

**File:** `configs/backup.toml`

Two strategy sections:

```toml
[batch]
# Paths staged locally and snapshotted by restic (versioned, deduplicated).
include = [...]
exclude = [...]


[[stream]]
# Streamed directly source → cloud via rclone sync (no local staging).
name = "..."
source = "..."
destination = "..."
exclude = [...]   # optional
```

Pydantic models (`BatchConfig`, `StreamSource`, `CompressSource`) enforce `extra="forbid"` —
unknown keys in the TOML raise a validation error at startup.

### Policy note: large-media (Jellyfin posters)

The example `configs/backup.toml` included with this repository intentionally
excludes Jellyfin poster/artwork from the batch staging and does not provide a
`jellyfin-metadata` `[[stream]]` entry by default. Rationale: artwork directories
contain a very large number of relatively small image files which greatly
increase upload and download times and can bloat cloud storage and snapshot
repositories. The project keeps small, critical items (databases, config) in
restic snapshots for versioning and integrity, streams large object stores (e.g.
MinIO) directly to cloud remotes, and compresses selected media where appropriate.

If you prefer to back up artwork, remove the `exclude` for
`volumes/jellyfin_data/metadata/**` and add a `[[stream]]` block targeting
an archive landing zone (pre-zipped or pre-aggregated), or accept
higher transfer counts.

### High-file-count buckets (example: minio:notebook)

Buckets containing very large numbers of small objects (for example
`minio:notebook`) can cause poor sync performance and high API overhead.
For these, prefer a dedicated `[[stream]]` block that targets a pre-zipped
or pre-aggregated destination, or accept higher transfer counts. This
reduces API overhead while still preserving content.

---

## Orchestrators

### `src/orchestrators/backup.py`

Runs stages in order: gather → restic → stream × N.
Each stage is wrapped in `run_checkpoint_stage` for resumability.

### `src/orchestrators/restore.py`

Runs stages in order: restic restore → stream × N (reversed).
Loads `BackupConfig` from `backup.toml` to drive the stream stages.

---

## Files

| File | Role |
|---|---|
| `src/ports/backup_stage.py` | `BackupStage` protocol (the port) |
| `src/adapters/rclone/stream_sync.py` | `RcloneStreamSync` — bidirectional sync adapter |
| `src/backup/stage_runner.py` | Generic `run_backup_stage` / `run_restore_stage` |
| `src/configuration/backup_config.py` | Pydantic config models |
| `src/orchestrators/backup.py` | Full backup pipeline |
| `src/orchestrators/restore.py` | Full restore pipeline (symmetric) |
| `configs/backup.toml` | Single control surface for all backup strategies |
| `src/configuration/backup_config.py` | Pydantic config models |
| `src/orchestrators/backup.py` | Full backup pipeline |
| `src/orchestrators/restore.py` | Full restore pipeline (symmetric) |
| `configs/backup.toml` | Single control surface for all backup strategies |
