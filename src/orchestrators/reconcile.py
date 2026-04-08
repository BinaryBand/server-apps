from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from argparse import ArgumentParser

from src.reconciler.core import reconcile_once


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
