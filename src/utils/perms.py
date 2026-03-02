from __future__ import annotations

from typing import Dict, Optional, Tuple
from pathlib import Path
import subprocess
import yaml  # type: ignore[import-untyped]
import os


def _run(cmd: list[str], dry_run: bool = False) -> None:
    print(" " + " ".join(cmd))
    if not dry_run:
        subprocess.check_call(cmd)


def ensure_group(name: str, gid: int, dry_run: bool = False) -> None:
    try:
        subprocess.check_output(["getent", "group", name], text=True)
        return
    except subprocess.CalledProcessError:
        pass
    _run(["groupadd", "-g", str(gid), name], dry_run=dry_run)


def ensure_user(
    name: str, uid: int, gid: int, comment: str, dry_run: bool = False
) -> None:
    try:
        subprocess.check_output(["id", "-u", name], text=True)
        return
    except subprocess.CalledProcessError:
        pass
    _run(
        [
            "useradd",
            "-M",
            "-s",
            "/usr/sbin/nologin",
            "-u",
            str(uid),
            "-g",
            str(gid),
            "-c",
            comment,
            name,
        ],
        dry_run=dry_run,
    )


def apply_volume(
    path: Path,
    owner_uid: int,
    owner_gid: int,
    mode: str = "0755",
    recurse: bool = False,
    dry_run: bool = False,
) -> None:
    chown_func = getattr(os, "chown", None)

    p = path.expanduser().resolve()
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
                        if chown_func is None:
                            raise RuntimeError("os.chown unavailable on this platform")
                        chown_func(target, owner_uid, owner_gid, follow_symlinks=False)
                        target.chmod(int(mode, 8))
                except PermissionError:
                    print(f"PermissionError setting {target}; run as root")
                except RuntimeError as e:
                    print(str(e))
                    return
    else:
        try:
            if not dry_run:
                if chown_func is None:
                    raise RuntimeError("os.chown unavailable on this platform")
                chown_func(p, owner_uid, owner_gid, follow_symlinks=False)
                p.chmod(int(mode, 8))
        except PermissionError:
            print(f"PermissionError setting {p}; run as root")
        except RuntimeError as e:
            print(str(e))


def apply_manifest(
    manifest_path: Path, repo_root: Path | None = None, dry_run: bool = False
) -> Dict[str, Tuple[int, int]]:
    """Apply the declarative permissions manifest. Returns user_map of created users.

    manifest_path: path to yaml manifest
    repo_root: base to resolve relative volume paths (defaults to manifest parent)
    """
    if repo_root is None:
        repo_root = manifest_path.resolve().parent

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    users = data.get("users", {})
    volumes = data.get("volumes", {})

    user_map: Dict[str, Tuple[int, int]] = {}
    for uname, uinfo in users.items():
        uid = int(uinfo.get("uid"))
        gid = int(uinfo.get("gid"))
        comment = uinfo.get("comment", uname)
        print(f"Ensure group {uname} (gid={gid})")
        ensure_group(uname, gid, dry_run=dry_run)
        print(f"Ensure user {uname} (uid={uid}) gid={gid})")
        ensure_user(uname, uid, gid, comment, dry_run=dry_run)
        user_map[uname] = (uid, gid)

    for vpath, vinfo in volumes.items():
        owner = vinfo.get("owner")
        group = vinfo.get("group")
        mode = vinfo.get("mode", "0755")
        recurse = bool(vinfo.get("recurse", False))

        if owner == "root" or owner is None:
            owner_uid = 0
        else:
            owner_uid: Optional[int] = user_map.get(owner, (None, None))[0]
            if owner_uid is None:
                print(f"Unknown owner '{owner}' for {vpath}; skipping")
                continue

        if group == "root" or group is None:
            owner_gid = 0
        else:
            owner_gid: Optional[int] = user_map.get(group, (None, None))[1]
            if owner_gid is None:
                print(f"Unknown group '{group}' for {vpath}; skipping")
                continue

        p = (repo_root / vpath).resolve()
        print(
            f"Applying ownership {owner_uid}:{owner_gid} mode={mode} recurse={recurse} to {p}"
        )
        apply_volume(p, owner_uid, owner_gid, mode, recurse, dry_run=dry_run)

    return user_map
