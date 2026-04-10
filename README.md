# Project Specification

## 0. Repository Map

- Infrastructure and scaffold ownership map: `docs/REPO_STRUCTURE.md`
- Python architecture and boundary rules: `docs/ARCHITECTURE.md`
- Contributor setup and quality gates: `docs/CONTRIBUTING.md`

## 1. Permissions chart

| Storage | Owner (source) | baikal | jellyfin | minio | rclone | restic |
| --- | ---: | :---: | :---: | :---: | :---: | :---: |
| `baikal_config` | baikal:baikal (baikal:8098→5573) | R/W | ✗ | ✗ | ✗ | ✗ |
| `baikal_data` | baikal:baikal (baikal) | R/W | ✗ | ✗ | ✗ | ✗ |
| `jellyfin_config` | jellyfin:jellyfin (jellyfin:8096→5572) | ✗ | R/W | ✗ | ✗ | ✗ |
| `jellyfin_data` | jellyfin:jellyfin (jellyfin) | ✗ | R/W | ✗ | ✗ | ✗ |
| `jellyfin_cache_data` | jellyfin:jellyfin (jellyfin) | ✗ | R/W | ✗ | ✗ | ✗ |
| `restic_repo_data` | — | ✗ | ✗ | ✗ | ✗ | R/W |
| `backups_data` | — | ✗ | ✗ | ✗ | ✗ | R/W |
| `rclone_config` | — | ✗ | ✗ | ✗ | R/— | ✗ |
| `MEDIA_MOUNT_DIR` (`/media` in rclone) | Host bind path (default `./runtime/media`) | ✗ | ✗ | ✗ | R/W | ✗ |
| `MEDIA_MOUNT_DIR` (`/media` in jellyfin) | Same host bind path (read-only, propagation enabled) | ✗ | R/— | ✗ | ✗ | ✗ |
| `LOGS_DIR` (`/logs`) | Host path | R/W | R/W | R/W | R/W | ✗ |
| `MINIO_DATA_DIR` (`/data`) | Host path | ✗ | ✗ | R/W | ✗ | ✗ |

## 1.1 Media Mount

Media is served through the rclone mount directly. Startup does not copy pCloud
media into a second local reader volume.

The host-side mountpoint lives under the repository runtime tree at
`./runtime/media` by default. Runtime artifacts should live under `./runtime`,
not under `./compose/runtime`.

```bash
./.venv/bin/python runbook/start.py
```

Startup does not include a media copy/sync stage.

## 1.2 Runtime Prerequisite

`runbook/start.py` runtime flow requires Docker daemon access from the current
shell user. Ensure `docker info` succeeds before running the runbooks.

## 2. Startup process

The startup pipeline runs four stages in order. Each stage is checkpointed — if
the process is interrupted, it resumes from the last incomplete stage.

```mermaid
stateDiagram-v2
  state "T0 - Starting" as Starting
  state "T1 - VolumesReady" as VolumesReady
  state "T2 - PermissionsApplied" as PermissionsApplied
  state "T3 - ComposeStarted" as ComposeStarted
  state "T4 - PostStartRunning" as PostStartRunning
  state "T5 - Healthy" as Healthy
  state "F1 - FailedPermissions" as FailedPermissions
  state "F2 - FailedCompose" as FailedCompose
  state "F3 - FailedPostStart" as FailedPostStart

  [*] --> Starting
  Starting --> VolumesReady: external volumes ensured
  VolumesReady --> PermissionsApplied: ansible runtime apply ok
  PermissionsApplied --> ComposeStarted: compose up ok
  ComposeStarted --> PostStartRunning: runtime post-start running
  PostStartRunning --> Healthy: checks pass
  Healthy --> [*]

  VolumesReady --> FailedPermissions: ansible apply fails
  PermissionsApplied --> FailedCompose: compose up fails
  PostStartRunning --> FailedPostStart: runtime checks fail

  FailedPermissions --> [*]
  FailedCompose --> [*]
  FailedPostStart --> [*]
```

| State | Ensure volumes | Apply permissions | Compose up | Post-start | Health checks | Transition |
| --- | :---: | :---: | :---: | :---: | :---: | --- |
| `T0` | ✗ | — | — | — | — | startup begins |
| `T1` | ✓ | — | — | — | — | volumes ok |
| `T2` | ✓ | ✓ | — | — | — | permissions ok |
| `T3` | ✓ | ✓ | ✓ | — | — | compose up ok |
| `T4` | ✓ | ✓ | ✓ | ✓ | — | post-start ok |
| `T5` | ✓ | ✓ | ✓ | ✓ | ✓ | health checks ok |
| `F1` | ✓ | ✗ | — | — | — | permissions failed from `T1` |
| `F2` | ✓ | ✓ | ✗ | — | — | compose failed from `T2` |
| `F3` | ✓ | ✓ | ✓ | ✓ | ✗ | runtime verification failed from `T4` |

> State names are defined in section 1 labels (for example, `T0 - Starting`, `F1 - FailedPermissions`).
