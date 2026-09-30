import importlib.util
from pathlib import Path
import sys
import json
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from build_username_benchmark import build, reported, summarize
from review_username_benchmark import address


def test_blocked_native_claims_remain_reported_but_not_false_positives():
    check = {"native_status": "CLAIMED", "verdict": "unknown", "address": "https://blocked.test/u/example", "reported": True}
    assert reported(check)
    stats = summarize([check], {})
    assert stats["reported"] == stats["unverified"] == stats["unknown_predictions"] == 1
    assert stats["source_contradicted"] == 0


def test_duplicate_endpoint_does_not_inflate_supported_profiles_or_shared_checks():
    url = "https://example.test/u/name"
    checks = [{"address": url, "reported": True, "verdict": "found"}] * 2
    stats = summarize(checks, {url: {"verdict": "found"}}, {url})
    assert stats["checked"] == stats["source_supported"] == stats["unique_reported"] == 1
    assert stats["raw_checks"] == stats["reported"] == 2
    assert stats["duplicates"] == 1


def test_source_contradiction_and_unverified_are_separate():
    checks = [{"address": "https://x.test/a", "reported": True, "verdict": "found"},
              {"address": "https://x.test/b", "reported": True, "verdict": "found"}]
    stats = summarize(checks, {"https://x.test/a": {"verdict": "not_found"}})
    assert stats["source_contradicted"] == stats["unverified"] == 1
    assert stats["source_supported"] == 0


def test_shared_scope_never_assumes_distinct_paths_or_schemes_equivalent():
    assert address("https://www.example.test/u/name/") == address("https://example.test/u/name")
    assert address("http://example.test/u/name") != address("https://example.test/u/name")
    assert address("https://example.test/u/name") != address("https://example.test/@name")


def test_builder_rejects_checkpoints_from_different_usernames(tmp_path):
    (tmp_path / "source-reviews.json").write_text("{}")
    for tool, username in (("myrecon", "first"), ("sherlock", "second")):
        (tmp_path / f"{tool}.json").write_text(json.dumps({"username": username,
            "controls": [{"username": username, "checks": {}, "duration_seconds": 1}],
            "metadata": {"status": "measured"}, "started_at_utc": "2026-09-30T00:00:00Z",
            "finished_at_utc": "2026-09-30T00:00:01Z"}))
    with pytest.raises(ValueError, match="same username"):
        build(tmp_path, tmp_path / "published.json")
    assert not (tmp_path / "published.json").exists()
