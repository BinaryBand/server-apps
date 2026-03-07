from pathlib import Path
import shutil
import os

TARGET_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not locate project root (no pyproject.toml found)")


def _remove_path(p: Path):
    try:
        shutil.rmtree(p)
        print(f"Removed {p}")
    except Exception:
        # ignore errors to keep behaviour simple
        pass


def main():
    root = _project_root()

    # Remove top-level matches first
    for name in TARGET_NAMES:
        _remove_path(root / name)

    # Walk tree and remove any matching directories at depth
    for dirpath, dirnames, _ in os.walk(root):
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
