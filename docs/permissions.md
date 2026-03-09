# Permissions Structure

This project centralizes permissions in declarative config and enforces them through Ansible before and during runtime.

## Architecture

```mermaid
flowchart LR
  subgraph Inputs
    PERM[/permissions.yml/]
    COMPOSE[/compose/base.yml/]
    ENV[(.env)]
  end

  subgraph Control
    START[start.py]
    RESET[_reset.py]
    POST[lifecycle/runtime_post_start.py]
  end

  subgraph Enforcement
    PLAY[apply-permissions.yml]
    DRIFT{ID drift assert}
    TASK[reconcile-startup.yml]
  end

  subgraph Outputs
    USERS([host users/groups])
    DIRS([bind dirs])
    VOLS([named volumes])
    STACK([compose services])
  end

  START --> PLAY
  RESET --> PLAY
  START --> POST

  PERM --> PLAY
  PERM --> DRIFT
  COMPOSE --> DRIFT
  ENV --> TASK

  PLAY --> DRIFT
  DRIFT --> TASK
  PLAY --> TASK
  POST --> STACK

  TASK --> USERS
  TASK --> DIRS
  TASK --> VOLS
  TASK --> STACK

  classDef data fill:#eef6ff,stroke:#4a7bb7,color:#1a365d
  classDef process fill:#eefaf0,stroke:#3a7a45,color:#1f4d2b
  classDef output fill:#fff8e8,stroke:#b07a12,color:#5c3d00

  class PERM,COMPOSE,ENV data
  class START,RESET,POST,PLAY,DRIFT,TASK process
  class USERS,DIRS,VOLS,STACK output
```

## Runtime Sequence

```mermaid
sequenceDiagram
  participant RB as Start Runbook
  participant AP as Permissions Playbook
  participant RS as Reconcile Tasks
  participant RP as Runtime PostStart
  participant DC as Docker Compose

  RB->>AP: run_permissions_playbook(mode=runtime)
  AP->>RS: load permissions manifest + env paths
  RS->>RS: assert fixed IDs match permissions users
  RS->>RS: ensure directories and runtime modes
  RS->>RS: ensure rclone config volume + render template
  RS->>DC: start stack from compose files
  RS->>RS: normalize jellyfin named volume ownership
  RB->>RP: run_runtime_post_start()
  RP->>DC: restart jellyfin
  RP->>DC: wait for minio readiness
  RP->>DC: ensure media bucket exists
  RB->>DC: compose up verification + health checks
```

## Key Rules

- IDs are centralized and fixed in Compose + permissions manifest, not user-facing env knobs.
- `.env` should carry path/secrets/runtime values, not ownership policy.
- Any ID drift between Compose and permissions manifest fails early in Ansible.
- Post-start runtime actions are toolbox-split under `src/utils/docker/post_start/` (Jellyfin + MinIO) and orchestrated by `src/utils/docker/lifecycle/runtime_post_start.py`.
