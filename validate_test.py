from __future__ import annotations

from pathlib import Path
from runpy import run_path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "scripts" / "testing" / "validate_test.py"
    run_path(str(target), run_name="__main__")
