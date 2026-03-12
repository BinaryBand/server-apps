# Start process flow

```mermaid
flowchart TD
    A[runbook/start.py] --> B[RunbookLock (locks_root)]
    A --> C[OperationCheckpoint (checkpoints_root/start.json)]

    subgraph Stage: volumes
      E[ensure_external_volumes()] --> F["docker volume inspect / create"]
      E --> G["compose/base.yml, compose/dev.yml"]
      E --> H[".env (dotenv)"]
    end

    C --> I[Stage: permissions]
    I --> J[run_permissions_playbook()]
    J --> K[ansible/apply-permissions.yml]
    J --> L[ansible/inventory.ini]
    J --> M[infra/permissions.yml]

    C --> N[Stage: runtime]
    N --> O[run_runtime_post_start()]
    O --> P["docker restart jellyfin"]
    O --> Q[ensure_minio_media_bucket() / wait_for_minio_ready()]
    Q --> R["docker exec minio mc ... (mc alias/set/mb/stat/anonymous)"]
    Q --> S["MINIO_ROOT_USER / MINIO_ROOT_PASSWORD or S3 keys (secrets)"]

    C --> T[Stage: health]
    T --> U[run_runtime_health_checks()]
    U --> V["docker exec rclone (test /config/rclone/rclone.conf)"]
    U --> W["docker exec rclone ls to MinIO / remote"]
    U --> X["docker exec jellyfin test -w /logs"]
    U --> Y["docker inspect jellyfin health"]

    subgraph Env/Secrets
        H
        S
        Z[RCLONE_REMOTE (env/secret)]
    end
    A --> Env/Secrets
```

Files & protocols referenced:

- **Compose files:** [compose/base.yml](compose/base.yml), [compose/dev.yml](compose/dev.yml)
- **Env:** `.env` (loaded via dotenv)
- **Docker CLI / Compose:** `docker compose`, `docker volume`, `docker exec`, `docker inspect`, `docker restart`
- **Ansible playbook:** [ansible/apply-permissions.yml](ansible/apply-permissions.yml), [ansible/inventory.ini](ansible/inventory.ini), [infra/permissions.yml](infra/permissions.yml)
- **MinIO tools:** `mc` inside `minio` container (alias/set/mb/stat/anonymous)
- **Rclone:** `rclone` inside `rclone` container (uses `/config/rclone/rclone.conf`)
- **Runtime state:** checkpoints in `runtime/checkpoints` (controlled via env `CHECKPOINTS_DIR`) and locks in `runtime/locks` (`LOCKS_DIR`)
- **Secrets / env vars:** `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `RCLONE_REMOTE`, `MEDIA_DATA_PATH`, `LOGS_DIR`

Brief notes:

- `start.py` orchestrates four stages: `volumes`, `permissions`, `runtime`, `health`.
- Checkpointing and `RUNBOOK_RESUME` allow skipping already-completed stages.
- Errors in a stage mark the checkpoint and exit with `Degraded`/`failed` state.

Troubleshooting: Baikal DB not writable

- Symptom: container logs show permission errors for `/var/www/baikal/Specific/db/db.sqlite` or sqlite cannot open the database.
- Cause: the `baikal_data` volume or the DB file is not owned/writable by the runtime UID:GID `8098:5573` expected by the `baikal` service.
- Quick checks:
  - Run a quick list of the volume contents:

```bash
docker run --rm -v baikal_data:/data alpine ls -la /data || true
```

- Inspect the file inside the volume (adjust path if your layout places files under a subdir):

```bash
docker run --rm -v baikal_data:/data alpine ls -la /data/db/db.sqlite || true
```

- Quick fixes (pick one):
  - Make the volume files owned by `8098:5573` (safe, one-line):

```bash
docker run --rm -v baikal_data:/data alpine sh -c 'chown -R 8098:5573 /data'
```

- Ensure the DB file is writable (example):

```bash
docker run --rm -v baikal_data:/data alpine sh -c 'chmod 664 /data/db/db.sqlite || true'
```

- Use Ansible/permissions playbook to reconcile ownership if you prefer the repo tooling:

```python
from src.utils.permissions import run_permissions_playbook
run_permissions_playbook(mode="runtime")
```

- Notes:
  - `BAIKAL_SKIP_CHOWN=1` prevents the image from attempting `chown` during startup (useful when the volume already has correct ownership). It does not fix incorrect ownership on the volume itself.
  - SQLite requires the containing directory and file be writable by the process UID. Ensure the directory `/var/www/baikal/Specific/db` is writable by `8098` as well.
