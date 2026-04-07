from __future__ import annotations

from src.configuration.state_model import WorkflowState
from src.toolbox.docker.compose import compose_service_names, probe_external_volume
from src.toolbox.docker.health import probe_container_health, probe_minio_media_public
from src.toolbox.docker.volumes import required_external_volume_names
from src.toolbox.io.state_helpers import upsert_condition


class RuntimeObserver:
    """Read-only runtime observer for reconciliation probes."""

    def probe_volumes(self, state: WorkflowState) -> bool:
        statuses: list[bool] = []
        for volume_name in required_external_volume_names():
            exists = probe_external_volume(volume_name)
            upsert_condition(
                state, f"volume:{volume_name}", "true" if exists else "false"
            )
            statuses.append(exists)
        return not all(statuses)

    def probe_services(self, state: WorkflowState) -> bool:
        statuses: list[bool] = []
        for service_name in compose_service_names():
            healthy = probe_container_health(service_name)
            upsert_condition(
                state, f"service:{service_name}", "true" if healthy else "false"
            )
            statuses.append(healthy)
        return not all(statuses)

    def probe_runtime(self, state: WorkflowState) -> bool:
        volumes_degraded = self.probe_volumes(state)
        services_degraded = self.probe_services(state)

        media_public = probe_minio_media_public()
        upsert_condition(state, "minio:media-public", "true" if media_public else "false")

        return any((volumes_degraded, services_degraded, not media_public))
