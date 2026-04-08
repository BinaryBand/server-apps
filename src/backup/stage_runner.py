from src.ports.backup_stage import BackupStage


def run_backup_stage(stage: BackupStage, name: str) -> None:
    print(f"[stage:{name}] Starting backup")
    stage.backup()


def run_restore_stage(stage: BackupStage, name: str) -> None:
    print(f"[stage:{name}] Starting restore")
    stage.restore()


__all__ = ["run_backup_stage", "run_restore_stage"]
