#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="File-level complexity gate for Lizard output")
    parser.add_argument(
        "paths", nargs="*", default=["src", "runbook"], help="Paths to scan (default: src runbook)"
    )
    parser.add_argument("--max-file-ccn-sum", type=int, default=35)
    parser.add_argument("--max-file-avg-ccn", type=float, default=4.5)
    parser.add_argument("--max-file-high-risk-funcs", type=int, default=2)
    parser.add_argument("--high-risk-ccn", type=int, default=6)
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def run_lizard_csv(python: str, paths: list[str]) -> str:
    cmd = [python, "-m", "lizard", *paths, "-C", "5", "-L", "25", "-a", "4", "--csv"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout


def to_ccn(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    if "." in value:
        return int(float(value))
    return int(value)


def _parse_csv_rows(lines: list[str], high_risk_ccn: int) -> dict[str, dict[str, float]]:
    file_stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0.0, "ccn_sum": 0.0, "high_risk": 0.0}
    )
    for row in lines:
        cols = [c.strip() for c in row.split(",")]
        if len(cols) < 11:
            continue
        file_path = cols[6].strip('"')
        ccn = to_ccn(cols[1])
        file_stats[file_path]["count"] += 1
        file_stats[file_path]["ccn_sum"] += ccn
        if ccn >= high_risk_ccn:
            file_stats[file_path]["high_risk"] += 1
    return dict(file_stats)


def _file_reasons(
    stats: dict[str, float], max_ccn_sum: int, max_avg_ccn: float, max_high_risk: int
) -> list[str]:
    count = int(stats["count"])
    ccn_sum = int(stats["ccn_sum"])
    avg_ccn = (stats["ccn_sum"] / count) if count else 0.0
    high_risk = int(stats["high_risk"])
    reasons: list[str] = []
    if ccn_sum > max_ccn_sum:
        reasons.append(f"ccn_sum={ccn_sum}>{max_ccn_sum}")
    if avg_ccn > max_avg_ccn:
        reasons.append(f"avg_ccn={avg_ccn:.2f}>{max_avg_ccn}")
    if high_risk > max_high_risk:
        reasons.append(f"high_risk_funcs={high_risk}>{max_high_risk}")
    return reasons


def _collect_violations(
    file_stats: dict[str, dict[str, float]],
    max_ccn_sum: int,
    max_avg_ccn: float,
    max_high_risk: int,
) -> list[str]:
    violations: list[str] = []
    for file_path, stats in sorted(file_stats.items()):
        reasons = _file_reasons(stats, max_ccn_sum, max_avg_ccn, max_high_risk)
        if reasons:
            violations.append(f"{file_path}: " + ", ".join(reasons))
    return violations


def _nonempty_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def main() -> None:
    args = parse_args()
    csv_text = run_lizard_csv(args.python, args.paths)
    lines = _nonempty_lines(csv_text)
    if not lines:
        print("No functions found in Lizard output.")
        return
    file_stats = _parse_csv_rows(lines, args.high_risk_ccn)
    violations = _collect_violations(
        file_stats, args.max_file_ccn_sum, args.max_file_avg_ccn, args.max_file_high_risk_funcs
    )
    if violations:
        print("File-level Lizard gate failed:")
        for v in violations:
            print(f"- {v}")
        raise SystemExit(1)
    print("File-level Lizard gate passed.")


if __name__ == "__main__":
    main()
