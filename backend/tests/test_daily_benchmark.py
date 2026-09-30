import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("daily_benchmark", Path(__file__).parents[1] / "tools/daily_benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


@pytest.mark.parametrize("platform,code,data,expected", [
    ("GitHub", 200, {"login": "octocat", "id": 1}, "found"),
    ("GitHub", 200, {"login": "another", "id": 1}, "unknown"),
    ("GitHub", 200, {"message": "failure"}, "unknown"),
    ("GitHub", 404, None, "not_found"),
    ("GitHub", 429, None, "unknown"),
    ("GitLab", 200, [], "not_found"),
    ("GitLab", 200, [{"username": "octocat", "id": 9}], "found"),
    ("GitLab", 200, [{"username": "someone", "id": 9}], "unknown"),
    ("GitLab", 403, [], "unknown"),
    ("Hacker News", 200, None, "not_found"),
    ("Hacker News", 200, {"id": "octocat", "created": 12}, "found"),
    ("Hacker News", 200, {}, "unknown"),
    ("Hacker News", 503, None, "unknown"),
])
def test_ground_truth_requires_explicit_account_evidence(platform, code, data, expected):
    assert benchmark.reference_label(platform, "octocat", code, data) == expected


def row(truth, actual):
    return {"reference": {"verdict": truth}, "myrecon": {"verdict": actual}}


def test_partial_sample_counts_errors_without_crediting_unknowns():
    rows = [row("found", "found"), row("found", "not_found"), row("not_found", "found"),
            row("not_found", "not_found"), row("not_found", "unknown"), row("unknown", "found")]
    stats = benchmark.summarize(rows, "myrecon")
    assert (stats["TP"], stats["TN"], stats["FP"], stats["FN"]) == (1, 1, 1, 1)
    assert stats["false_positive_rate_percent"] == 50
    assert stats["accuracy_percent"] == 50
    assert stats["scored"] == 4 and stats["total"] == 6
    assert stats["unknown"] == stats["unknown_negative"] == stats["unscored"] == 1


def test_outage_is_unavailable_not_zero_false_positives():
    stats = benchmark.summarize([row("not_found", "unknown"), row("unknown", "found")], "myrecon")
    assert stats["false_positive_rate_percent"] is None
    assert stats["accuracy_percent"] is None
    assert stats["coverage_percent"] == 0


def test_publish_replaces_same_day_and_preserves_previous_days(tmp_path):
    output = tmp_path / "benchmarks.json"
    first = {"started_at_utc": "2026-09-29T03:17:00Z", "finished_at_utc": "2026-09-29T03:19:00Z"}
    second = {"started_at_utc": "2026-09-30T03:17:00Z", "finished_at_utc": "2026-09-30T03:19:00Z"}
    benchmark.publish(first, output, {"id": "test"})
    benchmark.publish(second, output, {"id": "test"})
    second["finished_at_utc"] = "2026-09-30T04:00:00Z"
    benchmark.publish(second, output, {"id": "test"})
    data = json.loads(output.read_text())
    assert len(data["runs"]) == 2
    assert data["latest"] == second
    assert data["next_update_due_utc"] == "2026-10-01T04:00:00Z"


def test_percentiles_interpolate_and_handle_no_timings():
    assert benchmark.percentile([10, 2, 8, 4], .5) == 6
    assert benchmark.percentile([], .95) is None
