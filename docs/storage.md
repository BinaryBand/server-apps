# Storage Topology

This document describes how named volumes and host binds are wired, and how backup/restore flows move data through them.

## 1. Runtime Mount Topology

```mermaid
flowchart LR
  subgraph Host
    MEDIA[(MEDIA_DATA_PATH)]
    LOGS[(LOGS_DIR)]
    MINIO_BIND[(MINIO_DATA_DIR)]
  end

  subgraph ExternalNamedVolumes[External Named Volumes]
    JV_CFG[(jellyfin_config)]
    JV_DATA[(jellyfin_data)]
    BK_CFG[(baikal_config)]
    BK_DATA[(baikal_data)]
    RESTIC_REPO[(restic_repo_data)]
    BACKUPS[(backup_data)]
    RCLONE_CFG[(rclone_config)]
  end

  subgraph InternalNamedVolumes[Internal Named Volumes]
    J_CACHE[(jellyfin_cache_data)]
  end

  subgraph Services
    JELLYFIN[jellyfin]
    BAIKAL[baikal]
    MINIO[minio]
    RCLONE[rclone]
    RESTIC[restic on-demand]
  end

  JV_CFG --> JELLYFIN
  JV_DATA --> JELLYFIN
  J_CACHE --> JELLYFIN
  BK_CFG --> BAIKAL
  BK_DATA --> BAIKAL

  RESTIC_REPO --> RESTIC
  BACKUPS --> RESTIC
  RCLONE_CFG --> RCLONE

  MEDIA --> JELLYFIN
  MEDIA --> RCLONE
  LOGS --> JELLYFIN
  LOGS --> BAIKAL
  LOGS --> MINIO
  LOGS --> RCLONE
  MINIO_BIND --> MINIO
```

## 2. Compose Alias Resolution

```mermaid
flowchart TB
  subgraph ComposeAliases
    A1[cloud_jellyfin_config]
    A2[cloud_jellyfin_data]
    A3[cloud_baikal_config]
    A4[cloud_baikal_data]
    A5[restic_repo_data]
    A6[backups_data]
    A7[rclone_config_data]
  end

  subgraph DockerVolumeNames
    N1[(jellyfin_config)]
    N2[(jellyfin_data)]
    N3[(baikal_config)]
    N4[(baikal_data)]
    N5[(restic_repo_data)]
    N6[(backups_data)]
    N7[(rclone_config)]
  end

  A1 --> N1
  A2 --> N2
  A3 --> N3
  A4 --> N4
  A5 --> N5
  A6 --> N6
  A7 --> N7
```

## 3. Backup Data Path (Gather + Restic)

```mermaid
sequenceDiagram
  participant G as gather_stage
  participant RCL as rclone container
  participant APP as App mounts (/data/volumes/*)
  participant BAK as backups volume
  participant RES as restic container
  participant REP as restic repo volume

  G->>RCL: rclone sync /data -> /backups
  RCL->>APP: read-only logical mounts
  RCL->>BAK: write staged files
  RES->>BAK: read /backups
  RES->>REP: write snapshots
```

## 4. Restore Data Path (Restic + Apply)

```mermaid
sequenceDiagram
  participant REP as restic repo volume
  participant RES as restic container
  participant BAK as backups volume
  participant RCL as rclone container
  participant APP as app targets

  RES->>REP: read snapshot
  RES->>BAK: restore to /backups/restore
  RCL->>BAK: read restore tree
  RCL->>APP: apply per logical volume
  Note over APP: named volumes for jellyfin/baikal\nbind path for minio_data
```

## 5. Ownership / Control Boundaries

```mermaid
flowchart LR
  subgraph Config
    C1[compose/base.yml + compose/dev.yml]
    C2[infra/permissions.yml]
    C3[.env paths + secrets]
  end

  subgraph Orchestration
    O1[runbook/start.py]
    O2[ansible apply-permissions]
    O3[lifecycle/runtime_post_start.py]
  end

  subgraph Enforcement
    E1[ID drift assert]
    E2[directory modes/owners]
    E3[compose up]
    E4[jellyfin restart + minio bucket]
  end

  C1 --> E1
  C2 --> E1
  C2 --> E2
  C3 --> E2

  O1 --> O2
  O1 --> O3
  O2 --> E1
  O2 --> E2
  O2 --> E3
  O3 --> E4
```
