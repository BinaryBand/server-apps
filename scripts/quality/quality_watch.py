#!/home/owen/Documents/Dev/server-apps/.venv/bin/python

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

POLL_SECONDS = 1.0


def tree_signature(paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    for base in paths:
        if not base.exists():
            continue
        for file_path in sorted(base.rglob("*.py")):
            stat = file_path.stat()
            hasher.update(str(file_path).encode("utf-8"))
            hasher.update(str(stat.st_mtime_ns).encode("utf-8"))
            hasher.update(str(stat.st_size).encode("utf-8"))
    return hasher.hexdigest()


def run_and_mark(begin: str, end: str, args: list[str]) -> None:
    print(begin, flush=True)
    subprocess.run(args, check=False)
    print(end, flush=True)


def main() -> None:
    workspace = Path(__file__).resolve().parent.parent.parent
    python = workspace / ".venv" / "bin" / "python"
    scan_paths = [workspace / "src", workspace / "runbook"]

    last_signature = ""

    run_and_mark(
        "::VULTURE_BEGIN::",
        "::VULTURE_END::",
        [
            str(python),
            "-m",
            "vulture",
            "src",
            "runbook",
            "--min-confidence",
            "80",
        ],
    )

    while True:
        current_signature = tree_signature(scan_paths)

        if current_signature != last_signature:
            last_signature = current_signature
            run_and_mark(
                "::LIZARD_BEGIN::",
                "::LIZARD_END::",
                [
                    str(python),
                    "-m",
                    "lizard",
                    "src",
                    "runbook",
                    "-C",
                    "5",
                    "-L",
                    "25",
                    "-a",
                    "4",
                    "-w",
                ],
            )
            run_and_mark(
                "::LIZARD_FILE_BEGIN::",
                "::LIZARD_FILE_END::",
                [
                    str(python),
                    str(workspace / "scripts" / "quality" / "lizard_file_gate.py"),
                    "src",
                    "runbook",
                    "--max-file-ccn-sum",
                    "35",
                    "--max-file-avg-ccn",
                    "4.5",
                    "--max-file-high-risk-funcs",
                    "2",
                    "--high-risk-ccn",
                    "6",
                ],
            )

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
