# Ansible — Command Reference

All playbooks live under `ansible/playbooks/`. Run them from the **project root**.

## Inventory

```text
ansible/inventory.ini
```

---

## Command Matrix

| Purpose | Playbook | Modes / Flags |
| --- | --- | --- |
| Apply runtime permissions + start stack | `playbooks/runtime.yml` | `permissions_mode=runtime` (default) |
| Bootstrap host users/groups/ownership | `playbooks/runtime.yml` | `-e permissions_mode=bootstrap` |
| Reset volume ownership to current user | `playbooks/runtime.yml` | `-e permissions_mode=reset` |
| Provision external storage volumes | `playbooks/provision.yml` | — |
| Enforce systemd unit desired state | `playbooks/install-timers.yml` | — |
| Enforce SSH authorized keys | `playbooks/enforce-ssh.yml` | — |

---

## Required Environment Variables

| Variable | Used by | Notes |
| --- | --- | --- |
| `PCLOUD_ACCESS_TOKEN` | `runtime.yml` | pCloud OAuth token for rclone config |
| `PCLOUD_EXPIRY` | `runtime.yml` | pCloud token expiry timestamp |
| `MINIO_ROOT_USER` | `runtime.yml` | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | `runtime.yml` | MinIO admin password |
| `MEDIA_MOUNT_DIR` | `runtime.yml` | Override media mountpoint (default: `runtime/media`) |
| `LOGS_DIR` | `runtime.yml` | Override logs directory (default: `runtime/logs`) |
| `MINIO_DATA_DIR` | `runtime.yml` | Override MinIO data path (default: `./minio`) |

---

## Role Ownership

| Role | Responsibility |
| --- | --- |
| `identity` | Derive service UIDs/GIDs from compose config |
| `storage` | Create and permission host-bind volume directories |
| `rclone_config` | Render and install rclone config into internal Docker volume |
| `validate` | Post-startup assertions (Jellyfin media access, named volume ownership) |
| `minio_bucket` | Ensure MinIO media bucket is public |
| `systemd_enforcer` | Install/purge project-owned systemd timer units |
| `ssh_enforcer` | Enforce SSH authorized keys (exclusive mode) |

---

## Examples

```bash
# Standard runtime start (permissions + compose up)
ansible-playbook -i ansible/inventory.ini ansible/playbooks/runtime.yml

# Bootstrap new host (requires sudo for user/group creation)
ansible-playbook -i ansible/inventory.ini ansible/playbooks/runtime.yml \
  -e permissions_mode=bootstrap

# Enforce systemd timers
ansible-playbook -i ansible/inventory.ini ansible/playbooks/install-timers.yml

# Dry-run SSH key enforcement
ansible-playbook -i ansible/inventory.ini ansible/playbooks/enforce-ssh.yml --check --diff
```

---

## Manifest Files

| File | Purpose |
| --- | --- |
| `ansible/permissions.yml` | Declarative volume ownership and user definitions |
| `ansible/systemd_units.yml` | Desired systemd timer/service state |
| `ansible/ssh_access.yml` | Desired SSH authorized keys per user |
| `ansible/manifests/*.yml` | Bootstrap storage volume declarations |
