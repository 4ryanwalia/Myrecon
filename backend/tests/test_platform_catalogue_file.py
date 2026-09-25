"""Keep the downloadable platform catalogue aligned with the live engines."""

import json
import os
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, os.fspath(BACKEND))

from modules.sweep import CATALOGUE, EXTENDED  # noqa: E402
from modules.username_checker import PLATFORMS, STANDARD_LIMIT  # noqa: E402


def test_downloadable_catalogue_matches_the_active_standard_and_full_scans():
    manifest = json.loads((ROOT / "frontend" / "data" / "platforms.json").read_text(encoding="utf-8"))
    catalogues = manifest["catalogues"]
    expected_standard = [name for name, _url, _expected_status in PLATFORMS[:STANDARD_LIMIT]]
    expected_full = [platform["name"] for platform in CATALOGUE]
    expected_extended = [platform["name"] for platform in EXTENDED]

    assert catalogues["standard"]["count"] == STANDARD_LIMIT
    assert catalogues["standard"]["platforms"] == expected_standard
    assert catalogues["full"]["count"] == len(CATALOGUE)
    assert catalogues["full"]["platforms"] == expected_full
    assert catalogues["extended"]["count"] == len(EXTENDED)
    assert catalogues["extended"]["platforms"] == expected_extended
