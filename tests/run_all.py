"""
Test runner that executes each test module in its own subprocess.

The database engine is a module-level singleton (by design -- see
database/connection.py), which is correct for a single running Streamlit
process but means multiple test modules cannot each point it at a
different throwaway SQLite file within one shared Python process. Running
each module as its own subprocess gives every test file a clean,
independent database exactly as intended.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_DIR = Path(__file__).parent
TEST_MODULES = [
    "tests.test_foundation",
    "tests.test_auth_and_structure",
    "tests.test_registration_and_verification",
    "tests.test_ui_persistence",
]


def main() -> int:
    project_root = TEST_DIR.parent
    overall_ok = True
    for module in TEST_MODULES:
        print(f"\n{'=' * 70}\nRunning {module}\n{'=' * 70}")
        result = subprocess.run(
            [sys.executable, "-m", "unittest", module, "-v"],
            cwd=str(project_root),
        )
        if result.returncode != 0:
            overall_ok = False
    print(f"\n{'=' * 70}")
    print("ALL TEST MODULES PASSED" if overall_ok else "ONE OR MORE TEST MODULES FAILED")
    print("=" * 70)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
