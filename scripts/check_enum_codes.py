#!/usr/bin/env python3
"""CI: fail if detector code strings are absent from classification enum."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from tests.test_enum_codes_exhaustive import test_detector_codes_are_in_enum  # noqa: E402

if __name__ == "__main__":
    test_detector_codes_are_in_enum()
    print("enum codes OK")
