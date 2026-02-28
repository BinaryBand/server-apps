from dotenv import find_dotenv
from pathlib import Path
import shutil
import sys
import os

_ROOT = Path(find_dotenv()).parent
sys.path.insert(0, str(_ROOT))

TARGET_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def _remove_path(p: Path):
    try:
        shutil.rmtree(p)
        print(f"Removed {p}")
    except Exception:
        # ignore errors to keep behaviour simple
        pass


def main():
    # Remove top-level matches first
    for name in TARGET_NAMES:
        _remove_path(_ROOT / name)

    # Walk tree and remove any matching directories at depth
    for dirpath, dirnames, _ in os.walk(_ROOT):
        # iterate over a copy since we'll modify dirnames
        for d in list(dirnames):
            if d in TARGET_NAMES:
                full = Path(dirpath) / d
                _remove_path(full)
                # prevent os.walk from descending into the removed dir
                try:
                    dirnames.remove(d)
                except ValueError:
                    pass


if __name__ == "__main__":
    main()
