from src.ports.object_sync import CloudObjectSync


def stream_sync_stage(adapter: CloudObjectSync, name: str) -> None:
    print(f"[stage:stream-{name}] Starting stream sync")
    adapter.sync()


__all__ = ["stream_sync_stage"]
