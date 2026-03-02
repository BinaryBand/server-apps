#!/usr/bin/env python3
"""
Apply host permissions declared in infra/permissions.yml.

Usage: sudo ./scripts/apply-perms.py [--dry-run]

This script will:
 - Ensure groups and users exist (idempotent; will not modify existing mismatched entries).
 - Create volume directories if missing.
 - Apply ownership and modes (optionally recursively).

Requires: Python 3 and PyYAML (install with `pip3 install pyyaml`).
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.perms import apply_manifest


def main():
    import argparse

    if os.name != "posix":
        print("apply-perms is supported on Linux/Unix hosts only.", file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="infra/permissions.yml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        sys.exit(1)

    # Delegate to shared helper
    apply_manifest(manifest_path, repo_root=REPO_ROOT, dry_run=args.dry_run)

    print("Done.")


if __name__ == "__main__":
    main()
