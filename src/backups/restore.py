from pathlib import Path
import os
import shutil
import subprocess
from dotenv import load_dotenv

RCLONE_IMAGE = "rclone/rclone:latest"


def _run(cmd: list[str]) -> None:
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _resolve_host_restore_dir(repo_root: Path, target: str) -> Path | None:
    backups_root = repo_root / ".local" / "backups"
    if target == "/backups":
        return backups_root
    if target.startswith("/backups/"):
        relative = target.removeprefix("/backups/")
        return backups_root / relative
    return None


def _sync_dir_to_volume(source_dir: Path, volume_name: str) -> None:
    _run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            "RCLONE_CONFIG=/dev/null",
            "-v",
            f"{str(source_dir.resolve())}:/source:ro",
            "-v",
            f"{volume_name}:/dest",
            RCLONE_IMAGE,
            "sync",
            "/source",
            "/dest",
        ]
    )


def _apply_restored_volumes(
    repo_root: Path, project: str, host_restore_dir: Path
) -> None:
    candidate_roots = [
        host_restore_dir / "volumes",
        host_restore_dir / "backups" / "volumes",
    ]
    restore_volumes_root = next((p for p in candidate_roots if p.exists()), None)
    if restore_volumes_root is None:
        print(
            "No restored volume tree found. Checked: "
            + ", ".join(str(p) for p in candidate_roots)
        )
        return

    mappings = [
        ("jellyfin_config", f"{project}_jellyfin_config"),
        ("jellyfin_data", f"{project}_jellyfin_data"),
        ("baikal_config", f"{project}_baikal_config"),
        ("baikal_data", f"{project}_baikal_data"),
    ]

    for source_name, volume_name in mappings:
        source_dir = restore_volumes_root / source_name
        if not source_dir.exists():
            print(f"Skipping {source_name}; not present in restored snapshot.")
            continue
        print(f"Applying restored data: {source_name} -> {volume_name}")
        _sync_dir_to_volume(source_dir, volume_name)


def restore_snapshot(
    snapshot: str = "latest",
    target: str = "/backups/restore",
    project: str | None = None,
    no_apply_volumes: bool = False,
) -> None:
    """Run restic restore into `target` then copy restored volume trees back into docker volumes.

    - `snapshot`: restic snapshot id or 'latest'
    - `target`: restore path inside restic container (e.g. '/backups/restore')
    - `project`: compose project name used as volume name prefix; if None, uses cwd name
    - `no_apply_volumes`: if True, do not copy restored files into docker volumes
    """
    load_dotenv()
    from src.backups.restic_runner import run_restic_command

    repo_root = Path(__file__).resolve().parents[2]
    project = project or os.getenv("PROJECT_NAME") or repo_root.name

    host_restore_dir = _resolve_host_restore_dir(repo_root, target)
    if (
        host_restore_dir is not None
        and target == "/backups/restore"
        and host_restore_dir.exists()
    ):
        print(f"Clearing existing restore directory: {host_restore_dir}")
        shutil.rmtree(host_restore_dir)

    # perform restic restore
    run_restic_command(["restore", snapshot, "--target", target])

    if no_apply_volumes:
        return

    if host_restore_dir is None:
        print("Restore target is outside /backups; skipping volume apply step.")
        return

    _apply_restored_volumes(repo_root, project, host_restore_dir)
