#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLAYBOOK="$REPO_ROOT/ansible/apply-permissions.yml"
INVENTORY="$REPO_ROOT/ansible/inventory.ini"
ENV_FILE="$REPO_ROOT/.env"

MANIFEST_PATH="infra/permissions.yml"
CHECK_MODE="false"
PERMISSIONS_MODE="runtime"
PASSTHROUGH_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      if [[ $# -lt 2 ]]; then
        echo "--manifest requires a value" >&2
        exit 2
      fi
      MANIFEST_PATH="$2"
      shift 2
      ;;
    --dry-run)
      CHECK_MODE="true"
      shift
      ;;
    --runtime)
      PERMISSIONS_MODE="runtime"
      shift
      ;;
    --bootstrap)
      PERMISSIONS_MODE="bootstrap"
      shift
      ;;
    --reset)
      PERMISSIONS_MODE="reset"
      shift
      ;;
    *)
      PASSTHROUGH_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$MANIFEST_PATH" = /* ]]; then
  MANIFEST_RESOLVED="$MANIFEST_PATH"
else
  MANIFEST_RESOLVED="$REPO_ROOT/$MANIFEST_PATH"
fi

ANSIBLE_PLAYBOOK_BIN="$(command -v ansible-playbook || true)"
if [[ -z "$ANSIBLE_PLAYBOOK_BIN" && -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/ansible-playbook" ]]; then
  ANSIBLE_PLAYBOOK_BIN="${VIRTUAL_ENV}/bin/ansible-playbook"
fi
if [[ -z "$ANSIBLE_PLAYBOOK_BIN" && -x "$REPO_ROOT/.venv/bin/ansible-playbook" ]]; then
  ANSIBLE_PLAYBOOK_BIN="$REPO_ROOT/.venv/bin/ansible-playbook"
fi
if [[ -z "$ANSIBLE_PLAYBOOK_BIN" ]]; then
  echo "ansible-playbook is required. Install Ansible and try again." >&2
  exit 2
fi

if [[ ! -f "$PLAYBOOK" ]]; then
  echo "Ansible playbook not found: $PLAYBOOK" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

CMD=(
  "$ANSIBLE_PLAYBOOK_BIN"
  -i "$INVENTORY"
  "$PLAYBOOK"
  -e "manifest_path=$MANIFEST_RESOLVED"
  -e "repo_root=$REPO_ROOT"
  -e "permissions_mode=$PERMISSIONS_MODE"
  -e "reset_uid=$(id -u)"
  -e "reset_gid=$(id -g)"
)

if [[ "$CHECK_MODE" == "true" ]]; then
  CMD+=(--check)
fi

if [[ ${#PASSTHROUGH_ARGS[@]} -gt 0 ]]; then
  CMD+=("${PASSTHROUGH_ARGS[@]}")
fi

if [[ "$PERMISSIONS_MODE" == "bootstrap" && "$EUID" -ne 0 ]]; then
  echo "Bootstrap mode requires root to apply host ownership/users. Re-running with sudo..."
  exec sudo "${CMD[@]}"
fi

exec "${CMD[@]}"
