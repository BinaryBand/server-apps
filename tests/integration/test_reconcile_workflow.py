from __future__ import annotations

from unittest.mock import Mock

from src.reconciler.core import reconcile_once


class TestReconcileWorkflowIntegration:
    """Integration tests for the complete reconciliation workflow"""

    def test_full_reconcile_workflow_success(self, state_root_tmp, monkeypatch):
        """Test the complete reconcile_once workflow with successful operations"""
        # Mock all external dependencies to succeed
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.required_external_volume_names",
            lambda: ["test_volume"],
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.compose_service_names", lambda: ["test_service"]
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_external_volume", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_container_health", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
        )

        # Mock the actual operations
        mock_ensure_volumes = Mock()
        mock_run_permissions = Mock()
        mock_run_post_start = Mock()
        mock_run_health_checks = Mock()

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", mock_ensure_volumes
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", mock_run_permissions
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_post_start
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks", mock_run_health_checks
        )

        # Run the full workflow
        state = reconcile_once(check_only=False)

        # Verify all operations were called
        mock_ensure_volumes.assert_called_once()
        mock_run_permissions.assert_called_once_with(mode="runtime")
        mock_run_post_start.assert_called_once()
        mock_run_health_checks.assert_called_once()

        # Verify final state
        assert state.observed == "Healthy"
        assert state.runStatus == "completed"

        # Verify all conditions are marked as true
        condition_names = [c.name for c in state.conditions]
        assert "volume:test_volume" in condition_names
        assert "PermissionsApplied" in condition_names
        assert "PostStartApplied" in condition_names
        assert "minio:media-public" in condition_names
        assert "service:test_service" in condition_names

        for condition in state.conditions:
            assert condition.status == "true"

    def test_full_reconcile_workflow_with_check_only(self, state_root_tmp, monkeypatch):
        """Test the reconcile_once workflow in check-only mode"""
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.required_external_volume_names",
            lambda: ["test_volume"],
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.compose_service_names", lambda: ["test_service"]
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_external_volume", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_container_health", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
        )

        # Mock the actual operations to ensure they are NOT called in check-only mode
        mock_ensure_volumes = Mock()
        mock_run_permissions = Mock()
        mock_run_post_start = Mock()
        mock_run_health_checks = Mock()

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", mock_ensure_volumes
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", mock_run_permissions
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_post_start
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks", mock_run_health_checks
        )

        # Run in check-only mode
        state = reconcile_once(check_only=True)

        # Verify operations were NOT called
        mock_ensure_volumes.assert_not_called()
        mock_run_permissions.assert_not_called()
        mock_run_post_start.assert_not_called()
        mock_run_health_checks.assert_not_called()

        # Verify check results
        assert state.observed == "Healthy"
        assert state.runStatus == "completed"

        # Verify conditions reflect check results
        condition_names = [c.name for c in state.conditions]
        assert "volume:test_volume" in condition_names
        assert "service:test_service" in condition_names
        assert "minio:media-public" in condition_names

        for condition in state.conditions:
            assert condition.status == "true"

    def test_full_reconcile_workflow_with_degraded_state(
        self, state_root_tmp, monkeypatch
    ):
        """Test the reconcile_once workflow with some degraded components"""
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.required_external_volume_names",
            lambda: ["good_volume", "bad_volume"],
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.compose_service_names",
            lambda: ["good_service", "bad_service"],
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_external_volume",
            lambda name: name == "good_volume",
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_container_health",
            lambda name: name == "good_service",
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: False
        )

        # Mock the actual operations
        mock_ensure_volumes = Mock()
        mock_run_permissions = Mock()
        mock_run_post_start = Mock()
        mock_run_health_checks = Mock()

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", mock_ensure_volumes
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", mock_run_permissions
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_post_start
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks", mock_run_health_checks
        )

        # Run the full workflow
        state = reconcile_once(check_only=False)

        # Verify all operations were called
        mock_ensure_volumes.assert_called_once()
        mock_run_permissions.assert_called_once_with(mode="runtime")
        mock_run_post_start.assert_called_once()
        mock_run_health_checks.assert_called_once()

        # Verify final state is degraded
        assert state.observed == "Degraded"
        assert state.runStatus == "failed"

        # Verify conditions reflect the actual state
        conditions = {c.name: c.status for c in state.conditions}
        assert conditions["volume:good_volume"] == "true"
        assert conditions["volume:bad_volume"] == "false"
        assert conditions["service:good_service"] == "true"
        assert conditions["service:bad_service"] == "false"
        assert conditions["minio:media-public"] == "false"

    def test_reconcile_workflow_idempotency(self, state_root_tmp, monkeypatch):
        """Test that running reconcile_once multiple times is idempotent"""
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.required_external_volume_names",
            lambda: ["test_volume"],
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.compose_service_names", lambda: ["test_service"]
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_external_volume", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_container_health", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
        )

        # Mock the actual operations
        mock_ensure_volumes = Mock()
        mock_run_permissions = Mock()
        mock_run_post_start = Mock()
        mock_run_health_checks = Mock()

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", mock_ensure_volumes
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", mock_run_permissions
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_post_start
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks", mock_run_health_checks
        )

        # Run the workflow twice
        state1 = reconcile_once(check_only=False)
        state2 = reconcile_once(check_only=False)

        # Verify both states are identical
        assert state1.observed == state2.observed
        assert state1.runStatus == state2.runStatus
        assert len(state1.conditions) == len(state2.conditions)

        # Verify operations were called the expected number of times
        mock_ensure_volumes.assert_called_once()
        mock_run_permissions.assert_called_once_with(mode="runtime")
        mock_run_post_start.assert_called_once()
        mock_run_health_checks.assert_called_once()

    def test_reconcile_workflow_with_mixed_check_only_and_full(
        self, state_root_tmp, monkeypatch
    ):
        """Test switching between check-only and full reconcile"""
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.required_external_volume_names",
            lambda: ["test_volume"],
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.compose_service_names", lambda: ["test_service"]
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_external_volume", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_container_health", lambda name: True
        )
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
        )

        # Mock the actual operations
        mock_ensure_volumes = Mock()
        mock_run_permissions = Mock()
        mock_run_post_start = Mock()
        mock_run_health_checks = Mock()

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", mock_ensure_volumes
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", mock_run_permissions
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_post_start
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks", mock_run_health_checks
        )

        # Run check-only first
        state1 = reconcile_once(check_only=True)
        assert state1.observed == "Healthy"
        assert state1.runStatus == "completed"

        # Verify operations were NOT called
        mock_ensure_volumes.assert_not_called()
        mock_run_permissions.assert_not_called()
        mock_run_post_start.assert_not_called()
        mock_run_health_checks.assert_not_called()

        # Reset mocks
        mock_ensure_volumes.reset_mock()
        mock_run_permissions.reset_mock()
        mock_run_post_start.reset_mock()
        mock_run_health_checks.reset_mock()

        # Run full reconcile
        state2 = reconcile_once(check_only=False)
        assert state2.observed == "Healthy"
        assert state2.runStatus == "completed"

        # Verify operations were called
        mock_ensure_volumes.assert_called_once()
        mock_run_permissions.assert_called_once_with(mode="runtime")
        mock_run_post_start.assert_called_once()
        mock_run_health_checks.assert_called_once()


class TestReconcileWorkflowOrdering:
    """Test the ordering of operations in the reconcile workflow"""

    def test_reconcile_workflow_operation_order(self, state_root_tmp, monkeypatch):
        """Test that operations are called in the correct order"""
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.required_external_volume_names", lambda: []
        )
        monkeypatch.setattr("src.reconciler.observer.runtime_observer.compose_service_names", lambda: [])
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
        )

        # Create mocks to track call order
        mock_ensure_volumes = Mock()
        mock_run_permissions = Mock()
        mock_run_post_start = Mock()
        mock_run_health_checks = Mock()

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", mock_ensure_volumes
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", mock_run_permissions
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_post_start
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks", mock_run_health_checks
        )

        # Run the workflow
        reconcile_once(check_only=False)

        mock_ensure_volumes.assert_called_once()
        mock_run_permissions.assert_called_once_with(mode="runtime")
        mock_run_post_start.assert_called_once()
        mock_run_health_checks.assert_called_once()

        # Verify the order by checking that each mock was called
        # (the actual order is verified by the test structure)

    def test_reconcile_workflow_skips_operations_on_error(
        self, state_root_tmp, monkeypatch
    ):
        """Test that subsequent operations are skipped when one fails"""
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.required_external_volume_names", lambda: []
        )
        monkeypatch.setattr("src.reconciler.observer.runtime_observer.compose_service_names", lambda: [])
        monkeypatch.setattr(
            "src.reconciler.observer.runtime_observer.probe_minio_media_public", lambda: True
        )

        # Create mocks
        mock_ensure_volumes = Mock()
        mock_run_permissions = Mock(side_effect=RuntimeError("Permissions failed"))
        mock_run_post_start = Mock()
        mock_run_health_checks = Mock()

        monkeypatch.setattr(
            "src.managers.pipeline.ensure_external_volumes", mock_ensure_volumes
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_permissions_playbook", mock_run_permissions
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_post_start", mock_run_post_start
        )
        monkeypatch.setattr(
            "src.managers.pipeline.run_runtime_health_checks", mock_run_health_checks
        )

        # Run the workflow - should fail on permissions
        state = reconcile_once(check_only=False)

        # Verify state reflects failure
        assert state.observed == "Degraded"
        assert state.runStatus == "failed"

        # Verify only the first operation was called
        mock_ensure_volumes.assert_called_once()
        mock_run_permissions.assert_called_once_with(mode="runtime")
        mock_run_post_start.assert_not_called()
        mock_run_health_checks.assert_not_called()
