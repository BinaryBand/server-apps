from __future__ import annotations

from runbook.restore import DEFAULT_RESTORE_TARGET, main

from io import StringIO
from unittest import TestCase, main as unittest_main
from unittest.mock import patch


class RestoreRunbookTest(TestCase):
    def test_list_snapshots_mode_uses_listing_path(self) -> None:
        with (
            patch("runbook.restore.ArgumentParser.parse_args") as parse_args,
            patch(
                "runbook.restore.recent_snapshots",
                return_value="ID Time\nabc now\n",
            ) as list_snapshots,
            patch("runbook.restore.restore_snapshot") as restore_snapshot,
            patch("sys.stdout", new=StringIO()) as stdout,
        ):
            parse_args.return_value.snapshot = "latest"
            parse_args.return_value.list_snapshots = True
            parse_args.return_value.no_apply_volumes = False

            main()

        list_snapshots.assert_called_once_with()
        restore_snapshot.assert_not_called()
        self.assertIn("[stage:list] Listing recent snapshots", stdout.getvalue())
        self.assertIn("abc now", stdout.getvalue())

    def test_restore_mode_uses_default_target(self) -> None:
        with (
            patch("runbook.restore.ArgumentParser.parse_args") as parse_args,
            patch("runbook.restore.recent_snapshots") as list_snapshots,
            patch("runbook.restore.restore_snapshot") as restore_snapshot,
        ):
            parse_args.return_value.snapshot = "latest"
            parse_args.return_value.list_snapshots = False
            parse_args.return_value.no_apply_volumes = True

            main()

        list_snapshots.assert_not_called()
        restore_snapshot.assert_called_once_with("latest", DEFAULT_RESTORE_TARGET, True)


if __name__ == "__main__":
    unittest_main()
