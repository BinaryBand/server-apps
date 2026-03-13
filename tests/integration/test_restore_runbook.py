from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from src.orchestrators.restore import DEFAULT_RESTORE_TARGET, main


def test_list_snapshots_mode_uses_listing_path(monkeypatch, capsys) -> None:
    args = SimpleNamespace(snapshot="latest", list_snapshots=True, no_apply_volumes=False)

    list_snapshots = Mock(return_value="ID Time\nabc now\n")
    restore_snapshot = Mock()

    monkeypatch.setattr(
        "src.orchestrators.restore.ArgumentParser.parse_args",
        lambda self, *a, **k: args,
    )
    monkeypatch.setattr("src.orchestrators.restore.recent_snapshots", list_snapshots)
    monkeypatch.setattr("src.orchestrators.restore.restore_snapshot", restore_snapshot)

    main()

    list_snapshots.assert_called_once_with()
    restore_snapshot.assert_not_called()
    captured = capsys.readouterr()
    assert "[stage:list] Listing recent snapshots" in captured.out
    assert "abc now" in captured.out


def test_restore_mode_uses_default_target(monkeypatch) -> None:
    args = SimpleNamespace(snapshot="latest", list_snapshots=False, no_apply_volumes=True)

    list_snapshots = Mock()
    restore_snapshot = Mock()

    monkeypatch.setattr(
        "src.orchestrators.restore.ArgumentParser.parse_args",
        lambda self, *a, **k: args,
    )
    monkeypatch.setattr("src.orchestrators.restore.recent_snapshots", list_snapshots)
    monkeypatch.setattr("src.orchestrators.restore.restore_snapshot", restore_snapshot)

    main()

    list_snapshots.assert_not_called()
    restore_snapshot.assert_called_once_with("latest", DEFAULT_RESTORE_TARGET, True)

