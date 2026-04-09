# TODO Plan: Cleanup + Systemd Timers via Ansible

## Task 1: Code Cleanup

### `src/toolbox/core/config.py` ✅ (in progress)
- [x] Remove `from typing import Optional`
- [x] Narrow `except Exception:` on import guard → `except ImportError:`
- [x] `_RCLONE_CFG: Optional[RcloneConfig]` → `_RCLONE_CFG: RcloneConfig | None = None`
- [x] `-> Optional[RcloneConfig]` → `-> RcloneConfig | None`
- [x] Replace fragile `"_RCLONE_CFG" in globals()` check with `_RCLONE_CFG_LOADED: bool = False` sentinel
- [x] Add `as err` + `print(f"[config] ...")` to bare `except Exception:` on parse failure

### `src/storage/compose.py`
- [ ] Narrow `except Exception: return False` in `probe_external_volume` (line 45) → `except OSError as err:` with a print

### `src/orchestrators/backup.py`, `restore.py`, `stop.py`
- [ ] Add `-> None` return type to `def main():` in each file

### `src/workflows/checkpoint.py`
- [ ] Add module-level constant `_STAGE_COMPLETE = "true"` (line 49)
- [ ] Replace `c.status == "true"` with `c.status == _STAGE_COMPLETE`

### `src/toolbox/backups/gather.py`
- [ ] **Delete** — dead code, never imported anywhere; real `gather_stage` (with correct type hints) lives in `src/backup/gather.py`

---

## Task 2: Ansible Role — `backup_timer`

Runs `runbook/backup.py` daily via systemd. All new files:

```
ansible/roles/backup_timer/
  tasks/main.yml
  handlers/main.yml
  templates/
    server-apps-backup.service.j2
    server-apps-backup.timer.j2
```

**`server-apps-backup.service.j2`** key points:
- `Type=oneshot` — finite process
- `WorkingDirectory={{ server_apps_project_dir }}` — anchors `from_root` and `find_dotenv()` (reads `.env` for secrets; no `EnvironmentFile` needed)
- `ExecStart={{ server_apps_project_dir }}/.venv/bin/python runbook/backup.py` — uses Poetry venv
- `User={{ backup_service_user }}` — must be in the `docker` group
- `After=docker.service` / `Requires=docker.service`
- `Environment=RUNBOOK_LOCK_TIMEOUT={{ backup_lock_timeout | default(300) }}`

**`server-apps-backup.timer.j2`** key points:
- `OnCalendar=*-*-* 02:00:00`
- `RandomizedDelaySec=300` — up to 5 min jitter
- `Persistent=true` — fires missed run on next boot

**Playbook vars** (passed via `--extra-vars` or defaults):
- `server_apps_project_dir` — defaults to `playbook_dir ~ '/../..'` (repo root)
- `backup_service_user` — defaults to current user (`id -un`)
- `backup_lock_timeout` — default `300`

---

## Task 3: Ansible Role — `afloat_trigger`

POSTs to `http://127.0.0.1:18080/runs` daily to trigger afloat's podcast download. Lives in `server-apps/ansible/` (afloat has no Ansible infra of its own). All new files:

```
ansible/roles/afloat_trigger/
  tasks/main.yml
  handlers/main.yml
  templates/
    afloat-trigger.service.j2
    afloat-trigger.timer.j2
```

**`afloat-trigger.service.j2`** key points:
- `Type=oneshot`
- `User=nobody` — only fires a localhost curl, no filesystem access needed
- `ExecStart=/usr/bin/curl --silent --show-error --fail --retry 3 --retry-delay 10 --max-time 30 -X POST -H "Content-Type: application/json" -d "{}" {{ afloat_api_url }}/runs`
- `--fail` means HTTP 4xx/5xx (e.g. 409 Already Running) logs as failed unit — acceptable
- `After=network-online.target`

**`afloat-trigger.timer.j2`** key points:
- `OnCalendar=*-*-* 06:00:00` — after backup at 02:00, no resource contention
- `RandomizedDelaySec=300`
- `Persistent=true`

---

## New Playbook: `ansible/playbooks/install-timers.yml`

```yaml
---
# Usage:
#   ansible-playbook -i ansible/inventory.ini ansible/playbooks/install-timers.yml \
#     -e "server_apps_project_dir=/opt/server-apps" \
#     -e "backup_service_user=owen"
- name: Install automated task timers
  hosts: all
  gather_facts: false
  vars:
    server_apps_project_dir: "{{ project_dir | default(playbook_dir ~ '/../..') }}"
    backup_service_user: "{{ service_user | default(lookup('ansible.builtin.pipe', 'id -un')) }}"
    backup_lock_timeout: 300
    afloat_api_url: "http://127.0.0.1:18080"
  roles:
    - backup_timer
    - afloat_trigger
```

Both roles share a handler named `Reload systemd` — Ansible deduplicates by name within a play.

---

## Verification

1. `ruff check src/` and `ruff format --check src/` pass clean
2. `python runbook/quality/check_dead_code.py` — no new flags
3. After Ansible run: `systemd-analyze verify /etc/systemd/system/server-apps-backup.{service,timer}`
4. Manual test: `systemctl start server-apps-backup.service` → check `journalctl -u server-apps-backup`
5. Manual test: `systemctl start afloat-trigger.service` (afloat-api must be running) → check `journalctl -u afloat-trigger`
6. Confirm scheduled: `systemctl list-timers server-apps-backup.timer afloat-trigger.timer`
