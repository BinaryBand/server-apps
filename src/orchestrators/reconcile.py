from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reconciler.core import reconcile_once

from argparse import ArgumentParser


def main() -> None:
    parser = ArgumentParser(description="Run one reconciliation pass")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    state = reconcile_once(check_only=args.check_only)
    print(f"[reconcile] observed={state.observed} status={state.runStatus}")
    if state.runStatus == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
