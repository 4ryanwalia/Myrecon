"""Durable guest streams and job polls must expose the same two card identities."""
import json

import app as api
from services import scan_job_api as jobs_api


def test_live_job_cards_match_the_final_and_polled_guest_preview(monkeypatch):
    cards = [{"platform": name, "url": f"https://{name.lower()}.example/profile", "exists": True}
             for name in ("First", "Second", "HiddenThird")]
    job = {"id": "a" * 32, "username": "fixture", "scope": "standard", "deep": False,
           "uid": None, "checked": 3, "status": "scanning", "refs": [{"path": "chunk"}]}
    final = {"status": "ok", "query": {}, "results": {"profiles": list(reversed(cards))},
             "exposures": [{"email": "hidden@example.com"}]}
    reads = iter([job, {**job, "status": "complete"}])
    monkeypatch.setattr(jobs_api.jobs, "get", lambda _: next(reads))
    monkeypatch.setattr(jobs_api.jobs, "chunk", lambda *_: cards)
    monkeypatch.setattr(jobs_api.jobs, "result", lambda _: final)
    monkeypatch.setattr(jobs_api.scan_engine, "catalogue", lambda *_: cards)
    monkeypatch.setattr(jobs_api.time, "sleep", lambda _: None)
    monkeypatch.setattr("services.search._live_view", lambda row, _: row)
    emitted = [json.loads(line) for line in jobs_api.events(api, job["id"])]
    visible = [e["result"]["platform"] for e in emitted if e["type"] == "found"]
    assert visible == ["First", "Second"]
    assert [e["count"] for e in emitted if e["type"] == "found_locked"] == [1]
    projected = emitted[-1]["data"]
    assert [r["platform"] for r in projected["results"]["profiles"]] == visible
    assert jobs_api._visible(api, job, final) == projected
    assert "HiddenThird" not in json.dumps(emitted)
    assert "hidden@example.com" not in json.dumps(emitted)
    assert final["results"]["profiles"][0]["platform"] == "HiddenThird"
