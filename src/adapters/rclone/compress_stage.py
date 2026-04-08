import tempfile
import zipfile
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from src.configuration.backup_config import CompressSource
from src.toolbox.core.config import get_project_name
from src.toolbox.docker.volumes_config import storage_docker_mount_flags
from src.toolbox.docker.wrappers.rclone import rclone_copy, rclone_lsf


@dataclass
class CompressStage:
    """Adapter: compress files by parent directory and sync archives to a cloud remote.

    For each distinct parent directory that contains matching files, a zip archive
    is created and uploaded. The archive path encodes the restore destination so no
    separate manifest is needed:

        destination/alyssa-grenfell/thumbnails.zip
            → restore to source/alyssa-grenfell/thumbnails

    Both backup() and restore() share a host-side temp directory bind-mounted at
    /staging inside each disposable rclone container.
    """

    config: CompressSource

    def _docker_args(self, tmpdir: str) -> list[str]:
        # Mount the prepared config copy from the staging dir so the
        # container can run as a non-root user and still read rclone.conf.
        args: list[str] = ["-v", f"{tmpdir}/rclone_conf:/config/rclone:ro"]
        args += ["-e", "RCLONE_CONFIG=/config/rclone/rclone.conf"]
        args += ["--network", f"{get_project_name()}_default"]
        # Run container as the host UID:GID so files written into the
        # host tempdir are owned by the invoking user and removable later.
        args += ["--user", f"{os.getuid()}:{os.getgid()}"]
        args += ["-v", f"{tmpdir}:/staging"]
        return args

    def backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Copy rclone.conf from the docker volume into the staging
            # directory and make it readable by the host UID so the
            # non-root rclone container can read it.
            staging_conf_dir = Path(tmpdir) / "rclone_conf"
            staging_conf_dir.mkdir(parents=True, exist_ok=True)
            cp_cmd = (
                "docker run --rm -v rclone_config:/config/rclone:ro "
                f"-v {staging_conf_dir}:/staging alpine sh -c 'cp /config/rclone/rclone.conf /staging/rclone.conf && chown {os.getuid()}:{os.getgid()} /staging/rclone.conf && chmod 600 /staging/rclone.conf'"
            )
            subprocess.run(cp_cmd, shell=True, check=True)

            docker_args = self._docker_args(tmpdir)

            # List all matching files under source
            lsf_extra = [flag for p in self.config.patterns for flag in ("--include", p)]
            files = rclone_lsf(self.config.source, docker_args=docker_args, extra_args=lsf_extra)

            if not files:
                print(f"[compress:{self.config.name}] No matching files found")
                return

            # Group by immediate parent directory
            groups: dict[str, list[str]] = {}
            for f in files:
                parent = str(PurePosixPath(f).parent)
                groups.setdefault(parent, []).append(f)

            for parent_dir, group_files in groups.items():
                print(
                    f"[compress:{self.config.name}] Compressing {parent_dir}"
                    f" ({len(group_files)} files)"
                )
                self._backup_group(parent_dir, tmpdir, docker_args)

    def _backup_group(self, parent_dir: str, tmpdir: str, docker_args: list[str]) -> None:
        parent_posix = PurePosixPath(parent_dir)
        archive_stem = parent_posix.name or "root"

        # Download the source dir into /staging/download/<parent_dir>
        rclone_copy(
            f"{self.config.source}/{parent_dir}",
            f"/staging/download/{parent_dir}",
            docker_args=docker_args,
        )

        # Zip the downloaded directory on the host
        dl_dir = Path(tmpdir) / "download" / parent_dir
        archive_host_dir = Path(tmpdir) / "archives" / parent_dir
        archive_host_dir.mkdir(parents=True, exist_ok=True)
        archive_host_path = archive_host_dir.parent / f"{archive_stem}.zip"

        with zipfile.ZipFile(archive_host_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in sorted(dl_dir.rglob("*")):
                if fpath.is_file():
                    zf.write(fpath, fpath.relative_to(dl_dir))

        # Upload the archive directory to the cloud destination
        # /staging/archives/<parent_posix.parent> → destination/<parent_posix.parent>
        archive_container_dir = str(PurePosixPath("/staging/archives") / parent_posix.parent)
        cloud_dest_dir = _join_remote(self.config.destination, str(parent_posix.parent))
        rclone_copy(
            archive_container_dir,
            cloud_dest_dir,
            docker_args=docker_args,
            extra_args=["--include", f"{archive_stem}.zip"],
        )

    def restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            staging_conf_dir = Path(tmpdir) / "rclone_conf"
            staging_conf_dir.mkdir(parents=True, exist_ok=True)
            cp_cmd = (
                "docker run --rm -v rclone_config:/config/rclone:ro "
                f"-v {staging_conf_dir}:/staging alpine sh -c 'cp /config/rclone/rclone.conf /staging/rclone.conf && chown {os.getuid()}:{os.getgid()} /staging/rclone.conf && chmod 600 /staging/rclone.conf'"
            )
            subprocess.run(cp_cmd, shell=True, check=True)

            docker_args = self._docker_args(tmpdir)

            # List all zip archives at the cloud destination
            archives = rclone_lsf(
                self.config.destination,
                docker_args=docker_args,
                extra_args=["--include", "**/*.zip"],
            )

            if not archives:
                print(
                    f"[compress:{self.config.name}] No archives found"
                    f" at {self.config.destination}"
                )
                return

            for archive_rel in archives:
                self._restore_archive(archive_rel, tmpdir, docker_args)

    def _restore_archive(
        self, archive_rel: str, tmpdir: str, docker_args: list[str]
    ) -> None:
        # archive_rel e.g. "alyssa-grenfell/thumbnails.zip"
        archive_posix = PurePosixPath(archive_rel)
        archive_stem = archive_posix.stem                   # "thumbnails"
        archive_parent = str(archive_posix.parent)          # "alyssa-grenfell"
        # restore path relative to source: "alyssa-grenfell/thumbnails"
        restore_rel = _join_posix(archive_parent, archive_stem)

        print(f"[compress:{self.config.name}] Restoring {restore_rel}")

        # Download the archive from the cloud
        archive_container_dir = _join_posix("/staging/archives", archive_parent)
        cloud_archive_dir = _join_remote(self.config.destination, archive_parent)
        rclone_copy(
            cloud_archive_dir,
            archive_container_dir,
            docker_args=docker_args,
            extra_args=["--include", f"{archive_stem}.zip"],
        )

        # Unzip on the host
        archive_host_path = Path(tmpdir) / "archives" / archive_rel
        extract_path = Path(tmpdir) / "extract" / restore_rel
        extract_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_host_path, "r") as zf:
            zf.extractall(extract_path)

        # Copy extracted files back to source remote
        rclone_copy(
            f"/staging/extract/{restore_rel}",
            _join_remote(self.config.source, restore_rel),
            docker_args=docker_args,
        )


def _join_posix(base: str, segment: str) -> str:
    """Join posix path segments, collapsing '.' components."""
    result = PurePosixPath(base) / segment
    # Normalise away leading '.' so we don't produce "./foo" paths
    parts = [p for p in result.parts if p != "."]
    return str(PurePosixPath(*parts)) if parts else "."


def _join_remote(remote: str, segment: str) -> str:
    """Append a path segment to an rclone remote path (e.g. 'pcloud:Backups/X')."""
    if segment in ("", "."):
        return remote
    return f"{remote}/{segment}"


__all__ = ["CompressStage"]
