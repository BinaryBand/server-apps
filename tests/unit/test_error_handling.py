from __future__ import annotations

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from src.managers.reconciler import reconcile_once
from src.toolbox.core.ansible import run_permissions_playbook
from src.toolbox.core.secrets import minio_credentials
from src.toolbox.core.locking import RunbookLock
from src.toolbox.docker.health import run_runtime_health_checks
from src.toolbox.docker.post_start import run_runtime_post_start
from src.toolbox.docker.compose import ensure_external_volumes


class TestReconcilerErrorHandling:
    """Test error handling scenarios in reconciler.py"""

    def test_reconcile_once_handles_runtime_error_during_health_checks(
        self, state_root_tmp, monkeypatch
    ):
        """Test that RuntimeError during health checks is properly handled"""
        monkeypatch.setattr(
            "src.managers.reconciler.required_external_volume_names", lambda: []
        )
        monkeypatch.setattr("src.managers.reconciler.compose_service_names", lambda: [])
        monkeypatch.setattr(
            "src.managers.reconciler.probe_minio_media_public", lambda: True
        )

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", lambda: None
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", lambda **kwargs: None
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", lambda: None
        )
        monkeypatch.setattr("src.managers.pipeline.sync_media", lambda **kwargs: None)

        # Mock health checks to raise RuntimeError
        def mock_run_runtime_health_checks():
            raise RuntimeError("Health check failed")

        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks",
            mock_run_runtime_health_checks,
        )

        state = reconcile_once(check_only=False)

        assert state.observed == "Degraded"
        assert state.runStatus == "failed"
        condition = next(c for c in state.conditions if c.name == "RuntimeHealth")
        assert condition.status == "false"
        assert "Health check failed" in condition.message

    def test_reconcile_once_handles_runtime_error_during_permissions(
        self, state_root_tmp, monkeypatch
    ):
        """Test that RuntimeError during permissions playbook is properly handled"""
        monkeypatch.setattr(
            "src.managers.reconciler.required_external_volume_names", lambda: []
        )
        monkeypatch.setattr("src.managers.reconciler.compose_service_names", lambda: [])
        monkeypatch.setattr(
            "src.managers.reconciler.probe_minio_media_public", lambda: True
        )

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", lambda: None
        )
        monkeypatch.setattr("src.managers.pipeline.sync_media", lambda **kwargs: None)

        # Mock permissions playbook to raise RuntimeError
        def mock_run_permissions_playbook(*args, **kwargs):
            raise RuntimeError("Permissions failed")

        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook",
            mock_run_permissions_playbook,
        )

        state = reconcile_once(check_only=False)

        assert state.observed == "Degraded"
        assert state.runStatus == "failed"
        condition = next(c for c in state.conditions if c.name == "RuntimeHealth")
        assert condition.status == "false"
        assert "Permissions failed" in condition.message

    def test_reconcile_once_handles_runtime_error_during_post_start(
        self, state_root_tmp, monkeypatch
    ):
        """Test that RuntimeError during post-start is properly handled"""
        monkeypatch.setattr(
            "src.managers.reconciler.required_external_volume_names", lambda: []
        )
        monkeypatch.setattr("src.managers.reconciler.compose_service_names", lambda: [])
        monkeypatch.setattr(
            "src.managers.reconciler.probe_minio_media_public", lambda: True
        )

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", lambda: None
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", lambda **kwargs: None
        )
        monkeypatch.setattr("src.managers.pipeline.sync_media", lambda **kwargs: None)

        # Mock post-start to raise RuntimeError
        def mock_run_runtime_post_start():
            raise RuntimeError("Post-start failed")

        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_runtime_post_start
        )

        state = reconcile_once(check_only=False)

        assert state.observed == "Degraded"
        assert state.runStatus == "failed"
        condition = next(c for c in state.conditions if c.name == "RuntimeHealth")
        assert condition.status == "false"
        assert "Post-start failed" in condition.message


class TestHealthChecksErrorHandling:
    """Test error handling in health checks"""

    def test_wait_for_command_handles_command_failures(self):
        """Test that wait_for_command properly handles command failures"""
        from src.toolbox.docker.health import CommandWaitSpec, wait_for_command
        from subprocess import CompletedProcess

        failed = CompletedProcess(
            ["docker", "inspect", "nonexistent"],
            returncode=1,
            stdout="",
            stderr="container not found\n",
        )

        with patch("src.toolbox.docker.health._run_command", return_value=failed):
            with pytest.raises(RuntimeError) as err:
                wait_for_command(
                    CommandWaitSpec(
                        description="Wait for container",
                        command=["docker", "inspect", "nonexistent"],
                        timeout_seconds=1,
                        interval_seconds=0.1,
                    )
                )

        assert "Wait for container failed." in str(err.value)
        assert "docker inspect nonexistent" in str(err.value)
        assert "container not found" in str(err.value)

    def test_wait_for_container_health_handles_nonexistent_container(self):
        """Test that wait_for_container_health handles nonexistent containers"""
        from src.toolbox.docker.health import (
            ContainerHealthWaitSpec,
            wait_for_container_health,
        )

        with patch("src.toolbox.docker.health._run_command") as mock_run:
            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="No such container: nonexistent\n"
            )

            with pytest.raises(RuntimeError) as err:
                wait_for_container_health(
                    ContainerHealthWaitSpec(
                        description="Wait for nonexistent",
                        container="nonexistent",
                        timeout_seconds=1,
                        interval_seconds=0.1,
                    )
                )

        assert "Wait for nonexistent failed." in str(err.value)

    def test_run_runtime_health_checks_handles_multiple_failures(self):
        """Test that run_runtime_health_checks handles multiple service failures"""
        with patch("src.toolbox.core.config.rclone_remote", return_value="pcloud"):
            with patch(
                "src.toolbox.docker.health.wait_for_container_exec"
            ) as mock_exec:
                mock_exec.side_effect = RuntimeError("Service unavailable")

                with pytest.raises(RuntimeError) as err:
                    run_runtime_health_checks()

        assert "Service unavailable" in str(err.value)

    def test_preflight_reports_docker_socket_permission_denied(self):
        """Test docker preflight surfaces permission guidance for docker.sock denial"""
        from subprocess import CompletedProcess
        from src.toolbox.docker.health import ensure_docker_daemon_access

        denied = CompletedProcess(
            ["docker", "info"],
            returncode=1,
            stdout="",
            stderr="permission denied while trying to connect to the docker API at unix:///var/run/docker.sock",
        )

        with patch("subprocess.run", return_value=denied):
            with pytest.raises(RuntimeError) as err:
                ensure_docker_daemon_access()

        assert "Docker daemon access denied" in str(err.value)
        assert "/var/run/docker.sock" in str(err.value)


class TestAnsibleErrorHandling:
    """Test error handling in Ansible operations"""

    def test_run_permissions_playbook_handles_missing_playbook(self, monkeypatch):
        """Test that missing playbook file is handled gracefully"""
        from pathlib import Path

        # Mock repo_root to return a non-existent path
        monkeypatch.setattr(
            "src.toolbox.core.runtime.repo_root", lambda: Path("/nonexistent")
        )

        with pytest.raises(SystemExit):
            run_permissions_playbook(mode="runtime")

    def test_run_permissions_playbook_handles_playbook_failure(self, monkeypatch):
        """Test that playbook execution failures are handled"""

        # Mock successful playbook file existence check
        def mock_exists(self):
            return True

        monkeypatch.setattr("pathlib.Path.exists", mock_exists)
        monkeypatch.setattr("os.getuid", lambda: 1000)
        monkeypatch.setattr("os.getgid", lambda: 1000)

        # Mock subprocess.run to raise CalledProcessError
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Ansible failed")

            with pytest.raises(RuntimeError) as err:
                run_permissions_playbook(mode="runtime")

        assert "Ansible failed" in str(err.value)

    def test_run_permissions_playbook_runtime_adds_docker_socket_hint(
        self, monkeypatch
    ):
        """Test runtime mode wraps docker.sock permission failures with remediation"""

        def mock_exists(self):
            return True

        monkeypatch.setattr("pathlib.Path.exists", mock_exists)
        monkeypatch.setattr("os.getuid", lambda: 1000)
        monkeypatch.setattr("os.getgid", lambda: 1000)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception(
                "permission denied while trying to connect to the docker API at unix:///var/run/docker.sock"
            )

            with pytest.raises(RuntimeError) as err:
                run_permissions_playbook(mode="runtime")

        message = str(err.value)
        assert "Failed to run permissions playbook" in message
        assert "Runtime mode requires Docker daemon access" in message


class TestPostStartErrorHandling:
    """Test error handling in post-start operations"""

    def test_run_runtime_post_start_handles_jellyfin_restart_failure(self):
        """Test that Jellyfin restart failures are handled"""
        from subprocess import CalledProcessError

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = CalledProcessError(1, "docker restart")

            with pytest.raises(RuntimeError) as err:
                run_runtime_post_start()

        assert "failed to restart jellyfin" in str(err.value)


class TestVolumeErrorHandling:
    """Test error handling in volume operations"""

    def test_ensure_external_volumes_handles_creation_failures(self):
        """Test that volume creation failures are handled"""
        from subprocess import CalledProcessError

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = CalledProcessError(1, "docker volume create")

            # Should not raise exception, just log failure
            ensure_external_volumes()

    def test_probe_external_volume_handles_nonexistent_volume(self):
        """Test that nonexistent volumes are handled gracefully"""
        from src.toolbox.docker.volumes import probe_external_volume

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1)

            result = probe_external_volume("nonexistent")

        assert result is False


class TestLockingErrorHandling:
    """Test error handling in locking operations"""

    def test_runbook_lock_handles_timeout(self):
        """Test that lock timeout is handled properly"""
        with TemporaryDirectory() as temp_dir:
            first = RunbookLock("test", Path(temp_dir), timeout_seconds=0.1)
            second = RunbookLock("test", Path(temp_dir), timeout_seconds=0.1)

            first.acquire()
            try:
                with pytest.raises(RuntimeError) as err:
                    second.acquire()

                assert "lock is held" in str(err.value)
            finally:
                first.release()

    def test_runbook_lock_handles_permission_errors(self, monkeypatch):
        """Test that permission errors during lock creation are handled"""
        with TemporaryDirectory() as temp_dir:
            # Make the directory read-only to simulate permission error
            import stat

            Path(temp_dir).chmod(stat.S_IRUSR | stat.S_IXUSR)

            lock = RunbookLock("test", Path(temp_dir))

            with pytest.raises(RuntimeError):
                lock.acquire()

            # Restore permissions for cleanup
            Path(temp_dir).chmod(stat.S_IRWXU)


class TestConfigurationErrorHandling:
    """Test error handling in configuration operations"""

    def test_minio_credentials_handles_missing_credentials(self):
        """Test that missing MinIO credentials are handled"""
        with patch("src.toolbox.core.secrets.read_secret") as mock_read:
            mock_read.side_effect = lambda name, default=None: None

            with pytest.raises(RuntimeError) as err:
                minio_credentials()

        assert "Missing MinIO credentials" in str(err.value)

    def test_bind_mount_value_handles_invalid_paths(self):
        """Test that invalid bind mount paths are handled"""
        from src.toolbox.core.config import bind_mount_value

        # Test with invalid path
        result = bind_mount_value("INVALID_PATH", "/nonexistent")
        assert result == "/nonexistent"
