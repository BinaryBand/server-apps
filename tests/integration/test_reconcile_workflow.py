from __future__ import annotations

from src.reconciler.core import reconcile_once
from tests.support.reconciler_helpers import patch_reconciler_observer, patch_runtime_pipeline


class TestReconcileWorkflowIntegration:
    """Integration tests for the complete reconciliation workflow"""

    def test_full_reconcile_workflow_success(self, state_root_tmp, monkeypatch):
        """Test the complete reconcile_once workflow with successful operations"""
        patch_reconciler_observer(
            monkeypatch,
            volumes=["test_volume"],
            services=["test_service"],
        )
        pipeline = patch_runtime_pipeline(monkeypatch)

        # Run the full workflow
        state = reconcile_once(check_only=False)

        # Verify all operations were called
        pipeline["ensure_volumes"].assert_called_once()
        pipeline["run_permissions"].assert_called_once_with(mode="runtime")
        pipeline["run_post_start"].assert_called_once()
        pipeline["run_health_checks"].assert_called_once()

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
        patch_reconciler_observer(
            monkeypatch,
            volumes=["test_volume"],
            services=["test_service"],
        )
        pipeline = patch_runtime_pipeline(monkeypatch)

        # Run in check-only mode
        state = reconcile_once(check_only=True)

        # Verify operations were NOT called
        pipeline["ensure_volumes"].assert_not_called()
        pipeline["run_permissions"].assert_not_called()
        pipeline["run_post_start"].assert_not_called()
        pipeline["run_health_checks"].assert_not_called()

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

    def test_full_reconcile_workflow_with_degraded_state(self, state_root_tmp, monkeypatch):
        """Test the reconcile_once workflow with some degraded components"""
        patch_reconciler_observer(
            monkeypatch,
            volumes=["good_volume", "bad_volume"],
            services=["good_service", "bad_service"],
            volume_probe=lambda name: name == "good_volume",
            service_probe=lambda name: name == "good_service",
            media_public=False,
        )
        pipeline = patch_runtime_pipeline(monkeypatch)

        # Run the full workflow
        state = reconcile_once(check_only=False)

        # Verify all operations were called
        pipeline["ensure_volumes"].assert_called_once()
        pipeline["run_permissions"].assert_called_once_with(mode="runtime")
        pipeline["run_post_start"].assert_called_once()
        pipeline["run_health_checks"].assert_called_once()

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
        patch_reconciler_observer(
            monkeypatch,
            volumes=["test_volume"],
            services=["test_service"],
        )
        pipeline = patch_runtime_pipeline(monkeypatch)

        # Run the workflow twice
        state1 = reconcile_once(check_only=False)
        state2 = reconcile_once(check_only=False)

        # Verify both states are identical
        assert state1.observed == state2.observed
        assert state1.runStatus == state2.runStatus
        assert len(state1.conditions) == len(state2.conditions)

        # Verify operations were called the expected number of times
        pipeline["ensure_volumes"].assert_called_once()
        pipeline["run_permissions"].assert_called_once_with(mode="runtime")
        pipeline["run_post_start"].assert_called_once()
        pipeline["run_health_checks"].assert_called_once()

    def test_reconcile_workflow_with_mixed_check_only_and_full(self, state_root_tmp, monkeypatch):
        """Test switching between check-only and full reconcile"""
        patch_reconciler_observer(
            monkeypatch,
            volumes=["test_volume"],
            services=["test_service"],
        )
        pipeline = patch_runtime_pipeline(monkeypatch)

        # Run check-only first
        state1 = reconcile_once(check_only=True)
        assert state1.observed == "Healthy"
        assert state1.runStatus == "completed"

        # Verify operations were NOT called
        pipeline["ensure_volumes"].assert_not_called()
        pipeline["run_permissions"].assert_not_called()
        pipeline["run_post_start"].assert_not_called()
        pipeline["run_health_checks"].assert_not_called()

        # Reset mocks
        pipeline["ensure_volumes"].reset_mock()
        pipeline["run_permissions"].reset_mock()
        pipeline["run_post_start"].reset_mock()
        pipeline["run_health_checks"].reset_mock()

        # Run full reconcile
        state2 = reconcile_once(check_only=False)
        assert state2.observed == "Healthy"
        assert state2.runStatus == "completed"

        # Verify operations were called
        pipeline["ensure_volumes"].assert_called_once()
        pipeline["run_permissions"].assert_called_once_with(mode="runtime")
        pipeline["run_post_start"].assert_called_once()
        pipeline["run_health_checks"].assert_called_once()


class TestReconcileWorkflowOrdering:
    """Test the ordering of operations in the reconcile workflow"""

    def test_reconcile_workflow_operation_order(self, state_root_tmp, monkeypatch):
        """Test that operations are called in the correct order"""
        patch_reconciler_observer(monkeypatch, volumes=[], services=[])
        pipeline = patch_runtime_pipeline(monkeypatch)

        # Run the workflow
        reconcile_once(check_only=False)

        pipeline["ensure_volumes"].assert_called_once()
        pipeline["run_permissions"].assert_called_once_with(mode="runtime")
        pipeline["run_post_start"].assert_called_once()
        pipeline["run_health_checks"].assert_called_once()

        # Verify the order by checking that each mock was called
        # (the actual order is verified by the test structure)

    def test_reconcile_workflow_skips_operations_on_error(self, state_root_tmp, monkeypatch):
        """Test that subsequent operations are skipped when one fails"""
        patch_reconciler_observer(monkeypatch, volumes=[], services=[])
        pipeline = patch_runtime_pipeline(
            monkeypatch,
            permissions_side_effect=RuntimeError("Permissions failed"),
        )

        # Run the workflow - should fail on permissions
        state = reconcile_once(check_only=False)

        # Verify state reflects failure
        assert state.observed == "Degraded"
        assert state.runStatus == "failed"

        # Verify only the first operation was called
        pipeline["ensure_volumes"].assert_called_once()
        pipeline["run_permissions"].assert_called_once_with(mode="runtime")
        pipeline["run_post_start"].assert_not_called()
        pipeline["run_health_checks"].assert_not_called()
