#!/usr/bin/env bash
set -euo pipefail

# Wrapper for apply-perms.py; ensures Python is available and suggests sudo if not root.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/apply-perms.py"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install it and try again." >&2
  exit 2
fi

if [ "$EUID" -ne 0 ]; then
  echo "This script should be run as root to apply ownership changes. Re-running with sudo..."
  exec sudo python3 "$PY" "$@"
else
  python3 "$PY" "$@"
fi
