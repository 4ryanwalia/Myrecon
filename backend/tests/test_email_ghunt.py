"""Synthetic GHunt contract and execution safety tests; no live Google requests."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from modules.email_ghunt import enrich_ghunt_email, normalize_ghunt

EMAIL = "fixture@example.com"
ID = "100000000000000000001"


def payload():
    return {"status": "found", "query": EMAIL, "profile": {
        "personId": ID, "sourceIds": {"PROFILE": {"lastUpdated": "2020/01/01 12:00:00 (UTC)"}},
        "emails": {"PROFILE": {"value": EMAIL}, "CONTACT": {"value": "PRIVATE"}},
        "names": {"PROFILE": {"fullname": "Example Person"}, "CONTACT": {"fullname": "PRIVATE"}},
        "profilePhotos": {"PROFILE": {"url": "https://lh3.googleusercontent.com/example", "isDefault": False}},
        "inAppReachability": {"PROFILE": {"apps": ["Maps", "Photos"]}},
        "extendedData": {"gplusData": {"isEntrepriseUser": False}, "dynamiteData": {"customerId": "PRIVATE"}},
        "calendar": "PRIVATE", "password": "PRIVATE"}, "stats": {"Reviews": 5, "Ratings": 0, "Answers": True, "Other": "PRIVATE"}}


def configure(monkeypatch, tmp_path):
    executable, session = tmp_path / "python.exe", tmp_path / "session.m"
    executable.touch()
    session.touch()
    monkeypatch.setenv("EMAIL_GHUNT_ENABLED", "true")
    monkeypatch.setenv("GHUNT_PYTHON_EXECUTABLE", str(executable))
    monkeypatch.setenv("GHUNT_SESSION_FILE", str(session))


def test_public_projection():
    profile = normalize_ghunt(payload(), EMAIL)
    assert profile["fields"]["ID"] == ID
    assert profile["fields"]["Enterprise user"] == "No"
    assert profile["fields"]["Last profile edit"].startswith("2020/")
    assert "Last seen" not in profile["fields"]
    assert profile["stats"] == {"Reviews": 5, "Ratings": 0}
    assert profile["lists"]["Active Google apps"] == ["Maps", "Photos"]
    assert profile["reviews"] == []
    assert "PRIVATE" not in json.dumps(profile)


def test_normalization_works_in_an_isolated_runtime_without_enrichment_dependencies():
    backend = Path(__file__).resolve().parents[1]
    runtime = backend.parent / "output" / "ghunt-runtime-modern" / "Scripts" / "python.exe"
    interpreter = str(runtime) if runtime.is_file() else sys.executable
    # Run the real projection in a fresh -I interpreter. Blocking this import
    # also catches accidental dependency regressions when requests is installed
    # in a developer or CI environment. No session files or providers are used.
    script = """
import builtins
import json
import sys

original_import = builtins.__import__
def standard_library_projection(name, *args, **kwargs):
    if name == 'requests' or name.startswith('requests.') or name == 'modules.email_enrichment':
        raise ImportError('Unexpected enrichment dependency')
    return original_import(name, *args, **kwargs)
builtins.__import__ = standard_library_projection
sys.path.insert(0, sys.argv[1])
from modules.email_ghunt import normalize_ghunt, text
data = json.loads(sys.stdin.read())
assert text('abcd', 2) == 'ab'
assert text(42) == '42'
assert text(1.5) == '1.5'
assert text(True) == '' and text(None) == '' and text({}) == ''
profile = normalize_ghunt(data, data['query'])
assert profile['fields']['ID'] == data['profile']['personId']
assert 'PRIVATE' not in json.dumps(profile)
print(json.dumps({'normalized': True, 'reviews': profile['stats']['Reviews']}))
"""
    completed = subprocess.run([interpreter, "-I", "-c", script, str(backend)],
                               input=json.dumps(payload()), text=True, capture_output=True,
                               timeout=15, shell=False)
    assert completed.returncode == 0, "Isolated public projection failed"
    assert json.loads(completed.stdout) == {"normalized": True, "reviews": 5}


@pytest.mark.parametrize("change", ["query", "id", "container", "email"])
def test_identity_guard(change):
    data = payload()
    if change == "query": data["query"] = "other@example.com"
    if change == "id": data["profile"]["personId"] = "bad"
    if change == "container": data["profile"]["sourceIds"] = {"CONTACT": {}}
    if change == "email": data["profile"]["emails"]["PROFILE"]["value"] = "other@example.com"
    with pytest.raises(ValueError):
        normalize_ghunt(data, EMAIL)


@pytest.mark.parametrize("url", ["https://googleusercontent.com.evil.example/avatar", "file:///photo", "https://user@lh3.googleusercontent.com/photo", "https://localhost/photo"])
def test_bad_photo_url(url):
    data = payload()
    data["profile"]["profilePhotos"]["PROFILE"]["url"] = url
    assert normalize_ghunt(data, EMAIL)["avatar_url"] == ""


def test_disabled_and_unconfigured_do_not_spawn(monkeypatch):
    monkeypatch.setenv("EMAIL_GHUNT_ENABLED", "false")
    monkeypatch.setattr("modules.email_ghunt.subprocess.run", lambda *a, **k: pytest.fail("Unexpected process"))
    assert enrich_ghunt_email(EMAIL)["status"] == "disabled"
    monkeypatch.setenv("EMAIL_GHUNT_ENABLED", "true")
    monkeypatch.setenv("GHUNT_PYTHON_EXECUTABLE", "python")
    assert enrich_ghunt_email(EMAIL)["status"] == "unconfigured"


def test_concurrent_worker_is_bounded(monkeypatch):
    from modules.email_ghunt import _WORKER_SLOT
    monkeypatch.setenv("EMAIL_GHUNT_ENABLED", "true")
    _WORKER_SLOT.acquire()
    try:
        assert enrich_ghunt_email(EMAIL)["status"] == "rate_limited"
    finally:
        _WORKER_SLOT.release()


def test_bounded_process_and_cleanup(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    monkeypatch.setenv("PDL_API_KEY", "PRIVATE")
    directories = []
    def run(command, **kwargs):
        assert command[1] == "-I"
        assert command[3] == "--worker"
        assert EMAIL not in command
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 40
        assert kwargs["stdout"] is subprocess.DEVNULL and kwargs["stderr"] is subprocess.DEVNULL
        assert "PDL_API_KEY" not in kwargs["env"]
        assert json.loads(kwargs["input"])["email"] == EMAIL
        directories.append(Path(kwargs["cwd"]))
        Path(command[4]).write_text(json.dumps(payload()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr("modules.email_ghunt.subprocess.run", run)
    result = enrich_ghunt_email(EMAIL)
    assert result["status"] == "ok" and len(result["profiles"]) == 1
    assert not directories[0].exists()


@pytest.mark.parametrize("failure", ["timeout", "missing", "badjson", "oversize", "identity", "auth"])
def test_failures_do_not_become_negative_findings(monkeypatch, tmp_path, failure):
    configure(monkeypatch, tmp_path)
    def run(command, **kwargs):
        if failure == "timeout": raise subprocess.TimeoutExpired(command, 40, output="PRIVATE")
        if failure == "missing": return subprocess.CompletedProcess(command, 1)
        data = payload()
        if failure == "identity": data["query"] = "other@example.com"
        if failure == "auth": data = {"status": "authentication_required"}
        body = "bad json" if failure == "badjson" else "x" * 2_000_001 if failure == "oversize" else json.dumps(data)
        Path(command[4]).write_text(body, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr("modules.email_ghunt.subprocess.run", run)
    result = enrich_ghunt_email(EMAIL)
    assert result["profiles"] == []
    assert result["status"] == {"timeout": "timeout", "auth": "authentication_required"}.get(failure, "unavailable")
    assert "PRIVATE" not in str(result)
