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
import stat
import subprocess
from pathlib import Path

try:
    import yaml
except Exception:
    print("PyYAML is required. Install with: pip3 install pyyaml", file=sys.stderr)
    sys.exit(2)


def run(cmd, dry_run=False):
    print(" "+" ".join(cmd))
    if not dry_run:
        subprocess.check_call(cmd)


def ensure_group(name, gid, dry_run=False):
    # Check if group exists
    try:
        out = subprocess.check_output(["getent", "group", name], text=True)
        return
    except subprocess.CalledProcessError:
        pass

    # Create group with gid
    run(["groupadd", "-g", str(gid), name], dry_run=dry_run)


def ensure_user(name, uid, gid, comment, dry_run=False):
    try:
        out = subprocess.check_output(["id", "-u", name], text=True)
        return
    except subprocess.CalledProcessError:
        pass

    cmd = ["useradd", "-M", "-s", "/usr/sbin/nologin", "-u", str(uid), "-g", str(gid), "-c", comment, name]
    run(cmd, dry_run=dry_run)


def apply_volume(path, owner_uid, owner_gid, mode, recurse, dry_run=False):
    p = Path(path).expanduser().resolve()
    if not p.exists():
        print(f"Creating {p}")
        if not dry_run:
            p.mkdir(parents=True, exist_ok=True)

    if recurse:
        for root, dirs, files in os.walk(p):
            for name in dirs + files:
                target = Path(root) / name
                try:
                    if not dry_run:
                        os.chown(target, owner_uid, owner_gid, follow_symlinks=False)
                        target.chmod(int(mode, 8))
                except PermissionError:
                    print(f"PermissionError setting {target}; run as root")
    else:
        try:
            if not dry_run:
                os.chown(p, owner_uid, owner_gid, follow_symlinks=False)
                p.chmod(int(mode, 8))
        except PermissionError:
            print(f"PermissionError setting {p}; run as root")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="infra/permissions.yml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        sys.exit(1)

    data = yaml.safe_load(manifest_path.read_text()) or {}

    users = data.get("users", {})
    volumes = data.get("volumes", {})

    # Map service user keys to uid/gid
    user_map = {}
    for uname, uinfo in users.items():
        uid = int(uinfo.get("uid"))
        gid = int(uinfo.get("gid"))
        comment = uinfo.get("comment", uname)
        print(f"Ensure group {uname} (gid={gid})")
        ensure_group(uname, gid, dry_run=args.dry_run)
        print(f"Ensure user {uname} (uid={uid}) gid={gid})")
        ensure_user(uname, uid, gid, comment, dry_run=args.dry_run)
        user_map[uname] = (uid, gid)

    # Apply volumes
    repo_root = Path(__file__).resolve().parents[1]
    for vpath, vinfo in volumes.items():
        owner = vinfo.get("owner")
        group = vinfo.get("group")
        mode = vinfo.get("mode", "0755")
        recurse = bool(vinfo.get("recurse", False))

        # Resolve owner/group to uid/gid
        if owner == "root" or owner is None:
            owner_uid = 0
        else:
            owner_uid = user_map.get(owner, (None, None))[0]
            if owner_uid is None:
                print(f"Unknown owner '{owner}' for {vpath}; skipping")
                continue

        if group == "root" or group is None:
            owner_gid = 0
        else:
            owner_gid = user_map.get(group, (None, None))[1]
            if owner_gid is None:
                print(f"Unknown group '{group}' for {vpath}; skipping")
                continue

        # Resolve path relative to repo
        p = (repo_root / vpath).resolve()
        print(f"Applying ownership {owner_uid}:{owner_gid} mode={mode} recurse={recurse} to {p}")
        apply_volume(p, owner_uid, owner_gid, mode, recurse, dry_run=args.dry_run)

    print("Done.")


if __name__ == "__main__":
    main()
