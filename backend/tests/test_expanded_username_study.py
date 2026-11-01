import json
import csv
import hashlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from expanded_username_study import normalize, outcome, reference_evidence, tool_summary


@pytest.mark.parametrize("platform,handle,code,data,title,expected", [
    ("GitHub", "blue", 200, {"id": 1, "login": "someone"}, "", "unknown"),
    ("GitLab", "blue", 200, [], "", "not_found"),
    ("Hacker News", "blue", 200, None, "", "not_found"),
    ("Docker Hub", "blue", 403, {"id": 1, "username": "blue"}, "", "unknown"),
    ("Docker Hub", "blue", 200, {"id": "123", "username": "blue"}, "", "found"),
    ("Dev.to", "blue", 200, {"id": 1, "username": "blue"}, "", "unknown"),
    ("Dev.to", "blue", 200, {"id": 1, "username": "blue", "type_of": "user"}, "", "found"),
    ("npm", "blue", 401, {}, "", "unknown"),
    ("npm", "blue", 404, {}, "", "unknown"),
    ("Keybase", "blue", 200, {"status": {"code": 205}, "them": None}, "", "not_found"),
    ("Keybase", "blue", 200, {"status": {"code": 0}, "them": {"id": "x", "basics": {"username": "another"}}}, "", "unknown"),
    ("PyPI", "Blue", 200, None, "Client Challenge", "unknown"),
    ("PyPI", "Blue", 200, None, "Profile of Blue · PyPI", "found"),
    ("PyPI", "Blue", 200, None, "Profile of someone · PyPI", "unknown"),
    ("PyPI", "Blue", 404, None, "Client Challenge", "unknown"),
])
def test_references_require_current_account_evidence(platform, handle, code, data, title, expected):
    assert reference_evidence(platform, handle, code, data, title)[0] == expected


def test_denied_native_claim_retained_without_becoming_a_scored_false_positive():
    raw = {"status": SimpleNamespace(status=SimpleNamespace(name="CLAIMED")), "http_status": 419}
    result = normalize(raw)
    assert result["verdict"] == "unknown"
    assert result["native_status"] == "CLAIMED"
    rows = [{"reference": {"verdict": "not_found"}, "sherlock": result}]
    stats = tool_summary(rows, "sherlock")
    assert stats["FP"] == 0 and stats["source_contradicted_claims"] == 1
    assert stats["unresolved_checks"] == 1 and stats["coverage_percent"] == 0
    assert outcome(rows[0]["reference"], result) == "unresolved_prediction"


def test_unknown_reference_and_unknown_prediction_are_counted_once():
    rows = [{"reference": {"verdict": "unknown"}, "myrecon": {"verdict": "unknown"}},
            {"reference": {"verdict": "not_found"}, "myrecon": {"verdict": "found"}},
            {"reference": {"verdict": "found"}, "myrecon": {"verdict": "not_found"}}]
    stats = tool_summary(rows, "myrecon")
    assert stats["unresolved_checks"] == 1
    assert stats["FP"] == stats["FN"] == 1
    assert outcome(rows[0]["reference"], rows[0]["myrecon"]) == "unscored_reference"


def test_predeclared_manifest_keeps_fixtures_on_their_origin_platform():
    data = json.loads((Path(__file__).parents[1] / "data/username-study-controls.json").read_text(encoding="utf-8"))
    assert len(data["cases"]) == 35 and len(data["platforms"]) == 8
    assert len({(c["platform"], c["handle"].casefold()) for c in data["cases"]}) == 35
    for case in data["cases"]:
        if case["cohort"] == "synthetic_negative_candidate":
            assert len(case["handle"]) == 14 and case["handle"].isalnum()
            assert not case["fixture_sources"]
        else:
            for source in case["fixture_sources"]:
                rule = data["rules"][case["platform"]][source["tool"]]
                assert rule["rule"][source["field"]].casefold() == case["handle"].casefold()
                assert source["site_name"] == rule["site_name"]


def test_published_downloads_reconcile_every_outcome_and_checksum():
    from publish_username_study import EVIDENCE, validate
    directory = Path(__file__).parents[2] / 'frontend/assets/downloads' / EVIDENCE
    data = json.loads((directory / 'study.json').read_text(encoding='utf-8'))
    validate(data)
    rows = list(csv.DictReader(io.StringIO((directory / 'checks.csv').read_text(encoding='utf-8'))))
    assert len(rows) == 105
    assert len({(r['control_id'], r['tool']) for r in rows}) == 105
    assert hashlib.sha256((directory / 'controls.json').read_bytes()).hexdigest() == data['manifest_sha256']
    for row in rows:
        recorded = next(c for c in data['checks'] if c['id'] == row['control_id'])
        assert row['outcome'] == recorded[row['tool']]['outcome']
        assert row['reference_verdict'] == recorded['reference']['verdict']
    for line in (directory / 'SHA256SUMS.txt').read_text().splitlines():
        expected, filename = line.split('  ', 1)
        assert hashlib.sha256((directory / filename).read_bytes()).hexdigest() == expected
    with zipfile.ZipFile(directory / 'evidence.zip') as archive:
        for line in archive.read('CONTENTS.sha256').decode().splitlines():
            expected, filename = line.split('  ', 1)
            assert hashlib.sha256(archive.read(filename)).hexdigest() == expected
        assert archive.read('study.json') == (directory / 'study.json').read_bytes()
        assert archive.read('reproduction/expanded_username_study.py') == (Path(__file__).parents[1] / 'tools/expanded_username_study.py').read_bytes()


def test_publication_rejects_incomplete_or_relabelled_unknown_evidence():
    from publish_username_study import EVIDENCE, validate
    directory = Path(__file__).parents[2] / 'frontend/assets/downloads' / EVIDENCE
    data = json.loads((directory / 'study.json').read_text(encoding='utf-8'))
    data['summaries']['sherlock']['unresolved_checks'] = 0
    with pytest.raises(ValueError, match='reconcile'):
        validate(data)
    data['status'] = 'measuring_sherlock'
    with pytest.raises(ValueError, match='incomplete'):
        validate(data)
