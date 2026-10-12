"""Synthetic LinkedIn discovery and API contracts, without provider requests."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from services import email_linkedin_public as service

_REAL_DISCOVER_SOURCE = service._discover_source


EMAIL = "fixture@example.com"
URL = "https://www.linkedin.com/in/fixture-person"


def seed(basis="email_hash"):
    return service._seed(URL, basis, "https://en.gravatar.com/" + "a" * 32 + ".json")


@pytest.fixture(autouse=True)
def isolated_sources(monkeypatch):
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    monkeypatch.setattr(service, "_discover_source", lambda *args: pytest.fail("Unexpected public identity call"))
    monkeypatch.setattr(service, "enrich_linkedin_public", lambda *args: pytest.fail("Unexpected LinkedIn request"))


def discovery(monkeypatch, links=None, github="no_match", gravatar="found"):
    monkeypatch.setattr(service, "_discover_source", lambda email, provider: {
        "status": github if provider == "GitHub" else gravatar,
        "links": [] if provider == "GitHub" else (links if links is not None else [seed()])})


def details(enrichment, state="found"):
    enrichment["sources"].append({"provider": "Public JSON-LD", "status": state})
    if state == "found":
        enrichment["profiles"].append({"platform": "LinkedIn", "url": enrichment["profiles"][0]["url"],
                                      "source": "LinkedIn public JSON-LD", "profile_status": "ok",
                                      "display_name": "Example Person", "bio": "Public description", "location": "Example City",
                                      "avatar_url": "https://media.licdn.com/dms/image/fixture.jpg",
                                      "fields": {"Headline": "Example Engineer"},
                                      "current_work": [{"company": "Example Company", "title": "Engineer"}],
                                      "positions": [{"company": "Example Company", "title": "Engineer", "start": "2023", "current": True}],
                                      "education": [{"school": "Example School", "degree": "Example Degree", "field_of_study": "Example Subject"}]})
    return enrichment


def test_public_email_link_to_linkedin_career_without_other_lookup_fanout(monkeypatch):
    discovery(monkeypatch)
    monkeypatch.setattr(service, "enrich_linkedin_public", details)
    monkeypatch.setattr("modules.email_enrichment.enrich_email", lambda *a: pytest.fail("No paid profile pipeline"))
    monkeypatch.setattr("modules.email_public_profiles.enrich_linkedin_email", lambda *a: pytest.fail("No PDL"))
    monkeypatch.setattr("modules.email_ghunt.enrich_ghunt_email", lambda *a: pytest.fail("No Google lookup"))
    result = service.lookup_linkedin_public(EMAIL)
    assert result["query"] == {"email": EMAIL}
    assert result["status"] == "ok"
    profile = result["profiles"][0]
    assert profile["url"] == URL and profile["basis"] == "email_hash"
    assert profile["current_work"][0]["company"] == "Example Company"
    assert profile["positions"][0]["current"] is True
    assert profile["education"][0]["degree"] == "Example Degree"


@pytest.mark.parametrize("state", ["blocked", "authentication_required", "rate_limited", "unavailable", "timeout"])
def test_details_failure_keeps_the_established_profile(monkeypatch, state):
    discovery(monkeypatch)
    monkeypatch.setattr(service, "enrich_linkedin_public", lambda value: details(value, state))
    result = service.lookup_linkedin_public(EMAIL)
    assert result["status"] == "partial"
    assert result["profiles"][0]["url"] == URL
    assert result["profiles"][0]["details_status"] == state
    assert result["profiles"][0]["positions"] == []


def test_no_link_cannot_become_an_absent_linkedin_claim_or_a_guessed_handle(monkeypatch):
    discovery(monkeypatch, links=[], gravatar="no_match")
    result = service.lookup_linkedin_public(EMAIL)
    assert result["status"] == "unknown"
    assert result["profiles"] == []
    assert result["sources"][-1]["status"] == "unknown"


def test_disabled_reader_does_not_launch_identity_workers(monkeypatch):
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "false")
    assert service.lookup_linkedin_public(EMAIL)["status"] == "disabled"


def test_duplicates_preserve_nonhistorical_basis_and_fanout_is_bounded(monkeypatch):
    old = service._seed(URL, "historical_public_link", "https://github.com/fixture/repo/commit/" + "a" * 40)
    links = [seed(), service._seed(URL + "-two", "email_hash", seed()["evidence_url"]), service._seed(URL + "-three", "email_hash", seed()["evidence_url"])]
    monkeypatch.setattr(service, "_discover_source", lambda email, provider: {"status": "found", "links": [old] if provider == "GitHub" else links})
    called = []
    monkeypatch.setattr(service, "enrich_linkedin_public", lambda value: called.append(value["profiles"][0]["url"]) or details(value))
    result = service.lookup_linkedin_public(EMAIL)
    assert called == [URL, URL + "-two"]
    assert result["profiles"][0]["basis"] == "email_hash"


def test_private_details_fields_and_unmatched_profiles_are_rejected(monkeypatch):
    discovery(monkeypatch)

    def malicious(value):
        value = details(value)
        profile = value["profiles"][-1]
        profile.update(cookie="PRIVATE", email="PRIVATE", phone="PRIVATE", raw="PRIVATE")
        profile["fields"]["Password"] = "PRIVATE"
        profile["positions"][0]["token"] = "PRIVATE"
        profile["education"][0]["private_address"] = "PRIVATE"
        value["sources"][-1]["reason"] = "PRIVATE"
        return value

    monkeypatch.setattr(service, "enrich_linkedin_public", malicious)
    result = service.lookup_linkedin_public(EMAIL)
    assert "PRIVATE" not in json.dumps(result)
    assert set(result["profiles"][0]["fields"]) == {"Headline"}

    def different(value):
        value = details(value)
        value["profiles"][-1]["url"] = URL + "-other"
        return value

    monkeypatch.setattr(service, "enrich_linkedin_public", different)
    assert service.lookup_linkedin_public(EMAIL)["profiles"][0]["details_status"] == "unavailable"


def test_github_requires_exact_or_historical_email_evidence():
    profile = {"status": "found", "profile_status": "ok", "website": URL, "url": "https://github.com/fixture"}
    assert service._github_links(profile)["links"] == []
    profile["evidence"] = "Exact email published on this GitHub profile"
    assert service._github_links(profile)["links"][0]["basis"] == "exact_public_email"
    profile.update(evidence="Historical public commit", evidence_url="https://github.com/fixture/repo/commit/" + "a" * 40, commit_date="2020-01-01")
    assert service._github_links(profile)["links"][0]["basis"] == "historical_public_link"


def test_verified_github_bio_and_social_links_are_canonical_and_keep_author_evidence():
    profile = {"status": "found", "profile_status": "ok", "username": "fixture", "url": "https://github.com/fixture",
               "evidence": "Exact email published on this GitHub profile", "bio": "Work profile https://in.linkedin.com/in/fixture-person.",
               "website": "https://example.com"}
    socials = [{"provider": "linkedin", "url": "https://uk.linkedin.com/in/fixture-person-two"},
               {"url": URL}, {"url": "https://linkedin.com.evil.example/in/attacker"}]
    result = service._github_links(profile, socials)
    assert [link["url"] for link in result["links"]] == [URL, URL + "-two"]
    assert all(link["basis"] == "exact_public_email" and link["evidence_url"] == "https://github.com/fixture" for link in result["links"])
    profile.update(evidence="Historical author email", evidence_url="https://github.com/fixture/repo/commit/" + "a" * 40, commit_date="2020-01-01")
    assert all(link["basis"] == "historical_public_link" for link in service._github_links(profile, socials)["links"])
    profile.pop("evidence_url")
    assert service._github_links(profile, socials)["links"] == []


def test_social_accounts_use_only_verified_username_and_one_anonymous_bounded_request(monkeypatch):
    import requests
    profile = {"username": "fixture", "url": "https://github.com/fixture"}
    called = []

    class Reply:
        status_code = 200
        closed = False
        def iter_content(self, size):
            yield json.dumps([{"provider": "linkedin", "url": URL, "token": "PRIVATE"}]).encode()
        def close(self):
            self.closed = True
    reply = Reply()

    class Session:
        trust_env = True
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            assert self.trust_env is False
            assert url == "https://api.github.com/users/fixture/social_accounts"
            assert kwargs["timeout"] == (3, 5) and kwargs["stream"] is True and kwargs["allow_redirects"] is False
            assert "Authorization" not in kwargs["headers"] and "Cookie" not in kwargs["headers"]
            assert kwargs["params"] == {"per_page": 30}
            called.append(url)
            return reply

    monkeypatch.setattr(requests, "Session", Session)
    result = service._github_social_accounts(profile, time.monotonic() + 20)
    assert result == {"status": "ok", "accounts": [{"url": URL}]}
    assert len(called) == 1 and reply.closed
    assert "PRIVATE" not in json.dumps(result)


def test_unverified_or_mismatched_github_identity_never_queries_social_accounts(monkeypatch):
    from modules.email_lookup import EmailLookup
    real_social_accounts = service._github_social_accounts
    monkeypatch.setattr(EmailLookup, "github", lambda self, email: {
        "status": "found", "profile_status": "ok", "username": "fixture", "url": "https://github.com/fixture", "bio": URL})
    monkeypatch.setattr(service, "_github_social_accounts", lambda *args: pytest.fail("No exact author evidence"))
    assert service._github_discovery(EMAIL)["links"] == []
    import requests
    monkeypatch.setattr(requests, "Session", lambda: pytest.fail("No matching verified username"))
    assert real_social_accounts({"username": "attacker", "url": "https://github.com/fixture"}, time.monotonic() + 20)["status"] == "unknown"
    assert real_social_accounts({"username": "fixture", "url": "https://github.com/fixture"}, time.monotonic() + 7)["status"] == "timeout"


@pytest.mark.parametrize("social_state", ["timeout", "rate_limited", "unavailable"])
def test_social_failure_retains_github_website_and_bio_links(monkeypatch, social_state):
    from modules.email_lookup import EmailLookup
    profile = {"status": "found", "profile_status": "ok", "username": "fixture", "url": "https://github.com/fixture",
               "evidence": "Exact email published on this GitHub profile", "website": URL, "bio": URL + "-two"}
    monkeypatch.setattr(EmailLookup, "github", lambda self, email: profile)
    monkeypatch.setattr(service, "_github_social_accounts", lambda *args: {"status": social_state, "accounts": []})
    result = service._github_discovery(EMAIL)
    assert [link["url"] for link in result["links"]] == [URL, URL + "-two"]
    assert result["status"] == "found" and result["social_status"] == social_state


def test_social_failure_status_retained_separately_from_successful_profile(monkeypatch):
    monkeypatch.setattr(service, "_discover_source", lambda email, provider: {
        "status": "found", "links": [seed()], "social_status": "rate_limited"} if provider == "GitHub" else {"status": "no_match", "links": []})
    monkeypatch.setattr(service, "enrich_linkedin_public", details)
    result = service.lookup_linkedin_public(EMAIL)
    assert result["profiles"][0]["url"] == URL and result["status"] == "partial"
    source = next(row for row in result["sources"] if row["name"] == "GitHub public social links")
    assert source["status"] == "rate_limited"


def test_oversized_social_response_is_rejected_without_retaining_private_payload(monkeypatch):
    import requests
    class Reply:
        status_code = 200
        def iter_content(self, size):
            yield b"x" * 100_001
        def close(self):
            pass
    class Session:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, *args, **kwargs):
            return Reply()
    monkeypatch.setattr(requests, "Session", Session)
    result = service._github_social_accounts({"username": "fixture", "url": "https://github.com/fixture"}, time.monotonic() + 20)
    assert result == {"status": "unavailable", "accounts": []}


def test_gravatar_projects_all_public_owner_link_shapes_anonymously(monkeypatch):
    from modules import email_linkedin_public as parser

    body = {"entry": [{"verifiedAccounts": [{"url": URL}], "urls": [{"value": URL + "-two"}], "accounts": [{"url": URL}], "email": "PRIVATE"}]}

    class Reply:
        status_code = 200
        def iter_content(self, size):
            yield json.dumps(body).encode()
        def close(self):
            pass

    class Session:
        trust_env = True
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            assert self.trust_env is False
            assert EMAIL not in url
            assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
            assert "Cookie" not in kwargs["headers"] and "Authorization" not in kwargs["headers"]
            return Reply()

    monkeypatch.setattr(parser.requests, "Session", Session)
    result = service._gravatar_links(EMAIL)
    assert [link["url"] for link in result["links"]] == [URL, URL + "-two"]
    assert "PRIVATE" not in json.dumps(result)


def test_discovery_worker_receives_stdin_only_and_has_bounded_lifetime(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "PRIVATE")
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT", "PRIVATE")
    directories = []

    def run(command, **kwargs):
        assert EMAIL not in command
        assert json.loads(kwargs["input"])["email"] == EMAIL
        assert kwargs["timeout"] == 25 and kwargs["shell"] is False
        assert kwargs["stdout"] is subprocess.DEVNULL and kwargs["stderr"] is subprocess.DEVNULL
        assert "GITHUB_TOKEN" not in kwargs["env"] and "FIREBASE_SERVICE_ACCOUNT" not in kwargs["env"]
        directories.append(Path(kwargs["cwd"]))
        Path(command[-1]).write_text(json.dumps({"status": "found", "links": [seed()]}))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(service.subprocess, "run", run)
    assert _REAL_DISCOVER_SOURCE(EMAIL, "GitHub")["status"] == "found"
    assert not directories[0].exists()


def test_isolated_worker_bootstraps_without_any_provider_or_session_access(tmp_path):
    output = tmp_path / "public.json"
    # Unsupported provider selects the no-network branch while exercising the
    # real isolated-interpreter import path used by both discovery workers.
    completed = subprocess.run([sys.executable, "-I", str(Path(service.__file__).resolve()),
                                "--discovery-worker", "Unsupported", str(output)],
                               input=json.dumps({"email": EMAIL}), text=True, capture_output=True,
                               timeout=15, shell=False)
    assert completed.returncode == 0, "Isolated discovery worker could not start"
    assert json.loads(output.read_text()) == {"status": "unavailable", "links": []}


def test_discovery_timeout_preserves_the_other_source(monkeypatch):
    monkeypatch.setattr(service, "_discover_source", lambda email, provider: {"status": "timeout", "links": []} if provider == "GitHub" else {"status": "found", "links": [seed()]})
    monkeypatch.setattr(service, "enrich_linkedin_public", details)
    result = service.lookup_linkedin_public(EMAIL)
    assert result["status"] == "partial"
    assert result["profiles"][0]["display_name"] == "Example Person"


def test_linkedin_endpoint_validates_and_does_not_cache_or_accept_url_claims(monkeypatch):
    import app as appmod
    import config
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
    calls = []
    monkeypatch.setattr(service, "lookup_linkedin_public", lambda email: calls.append(email) or {"status": "unknown", "query": {"email": email}, "profiles": [], "sources": []})
    client = appmod.create_app().test_client()
    assert client.post("/api/email/linkedin-public", json={"email": "bad"}).status_code == 422
    for _ in range(2):
        response = client.post("/api/email/linkedin-public", json={"email": EMAIL, "profile_url": URL + "-unverified"})
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.get_json()["status"] == "unknown"
    assert calls == [EMAIL, EMAIL]
    assert client.options("/api/email/linkedin-public").status_code == 204
