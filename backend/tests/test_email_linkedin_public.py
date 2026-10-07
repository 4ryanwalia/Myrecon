"""Synthetic public HTML contract and transport tests, never real identities."""
import json

import pytest

from modules.email_linkedin_public import bounded_text, enrich_linkedin_public, enrich_public_linkedin, linkedin_url, parse_public_profile

URL = "https://www.linkedin.com/in/fixture-person"


def html(person=None):
    person = person or {"@type": "Person", "url": URL, "name": "Fixture Person", "description": "Public biography",
                        "jobTitle": "Example Engineer", "image": {"contentUrl": "https://media.licdn.com/dms/image/fixture.jpg"},
                        "homeLocation": {"address": {"addressLocality": "Fixture City", "addressRegion": "Fixture Region", "streetAddress": "PRIVATE"}},
                        "worksFor": [{"@type": "OrganizationRole", "roleName": "Engineer", "startDate": "2023-12", "worksFor": {"name": "Fixture Company"}}],
                        "alumniOf": [{"@type": "EducationalOrganization", "name": "Fixture School"}], "email": "PRIVATE", "telephone": "PRIVATE"}
    return '<html><script type="application/ld+json">' + json.dumps({"@graph": [person]}) + "</script></html>"


def established():
    return {"profiles": [{"platform": "LinkedIn", "url": URL, "basis": "provider_email", "profile_status": "ok", "display_name": "Original positive"}], "sources": []}


class Reply:
    def __init__(self, body, status=200, content_type="text/html"):
        self.body, self.status_code, self.headers, self.closed = body, status, {"Content-Type": content_type}, False

    def iter_content(self, size):
        yield self.body.encode()

    def close(self):
        self.closed = True


class Session:
    def __init__(self, replies):
        self.replies, self.calls, self.trust_env, self.headers = list(replies), [], True, {}
        self.cookies = type("Cookies", (), {"clear": lambda self: None})()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        assert self.trust_env is False
        assert kwargs["timeout"] == (3, 5) and kwargs["allow_redirects"] is False and kwargs["stream"] is True
        assert "Authorization" not in self.headers and "Cookie" not in self.headers
        self.calls.append(url)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_schema_projection_matches_url_and_omits_sensitive_extras():
    profile = parse_public_profile(html(), URL)
    assert profile["display_name"] == "Fixture Person"
    assert profile["bio"] == "Public biography"
    assert profile["fields"]["Headline"] == "Example Engineer"
    assert profile["positions"] == [{"company": "Fixture Company", "title": "Engineer", "start": "2023-12"}]
    assert profile["education"] == [{"school": "Fixture School"}]
    assert profile["location"] == "Fixture City, Fixture Region"
    assert "PRIVATE" not in str(profile)
    assert "current" not in profile["positions"][0]
    assert "Connections" not in profile["fields"]


def test_plain_public_employer_and_explicit_education_fields_are_projected():
    person = {"@type": "Person", "url": URL, "jobTitle": "Example Engineer",
              "worksFor": [{"@type": "Organization", "name": "Current Example Company"}],
              "alumniOf": [{"@type": "Role", "alumniOf": {"name": "Example School"},
                            "degree": "Example Degree", "fieldOfStudy": "Example Subject",
                            "startDate": "2016", "endDate": "2020"}]}
    profile = parse_public_profile(html(person), URL)
    assert profile["current_work"] == [{"company": "Current Example Company", "title": "Example Engineer"}]
    assert profile["education"] == [{"school": "Example School", "degree": "Example Degree", "field_of_study": "Example Subject", "start": "2016", "end": "2020"}]


@pytest.mark.parametrize("extra,expected", [({}, None), ({"endDate": "Present"}, True),
                                          ({"endDate": "current"}, True), ({"current": False}, False),
                                          ({"isCurrent": True}, True)])
def test_role_current_status_requires_explicit_public_evidence(extra, expected):
    role = {"@type": "OrganizationRole", "worksFor": {"name": "Example Company"}, "roleName": "Engineer", **extra}
    person = {"@type": "Person", "url": URL, "worksFor": [role]}
    profile = parse_public_profile(html(person), URL)
    if expected is None:
        assert "current" not in profile["positions"][0]
    else:
        assert profile["positions"][0]["current"] is expected
    assert bool(profile["current_work"]) is (expected is True)


def test_current_flag_with_concrete_end_date_keeps_history_and_does_not_promote_employer():
    from services.email_linkedin_public import _current_work
    person = {"@type": "Person", "url": URL, "worksFor": [{
        "@type": "OrganizationRole", "worksFor": {"name": "Former Example Company"},
        "roleName": "Engineer", "startDate": "2020", "endDate": "2023", "current": True}]}
    profile = parse_public_profile(html(person), URL)
    assert profile["positions"] == [{"company": "Former Example Company", "title": "Engineer", "start": "2020", "end": "2023"}]
    assert profile["current_work"] == []
    assert _current_work([{"company": "Former Example Company", "title": "Engineer", "current": True, "end": "2023"}]) == []


def test_explicit_false_overrides_present_marker_and_does_not_promote_employer():
    from services.email_linkedin_public import _current_work
    person = {"@type": "Person", "url": URL, "worksFor": [{
        "@type": "OrganizationRole", "worksFor": {"name": "Example Company"},
        "roleName": "Engineer", "endDate": "Present", "current": False}]}
    profile = parse_public_profile(html(person), URL)
    assert profile["positions"][0]["current"] is False
    assert profile["positions"][0]["end"] == "Present"
    assert profile["current_work"] == []
    assert _current_work([{"company": "Example Company", "title": "Engineer", "current": False, "end": "Present"}]) == []


@pytest.mark.parametrize("value", ["http://linkedin.com/in/example", "https://linkedin.com.evil.example/in/example", "https://user@linkedin.com/in/example", "https://linkedin.com:444/in/example", "https://linkedin.com/company/example", "https://linkedin.com/in/a/../x", "https://localhost/in/example", "https://linkedin.com/in/example%2fadmin", None])
def test_url_restrictions(value):
    assert linkedin_url(value) == ""


@pytest.mark.parametrize("host", ["in.linkedin.com", "uk.linkedin.com", "de.linkedin.com"])
def test_country_profile_hosts_canonicalize_to_fixed_public_host(host):
    assert linkedin_url("https://" + host + "/in/fixture-person/?tracking=ignored") == URL


@pytest.mark.parametrize("host", ["evil.linkedin.com", "www.in.linkedin.com", "in.linkedin.com.evil.example", "a1.linkedin.com", "i.linkedin.com"])
def test_arbitrary_or_nested_linkedin_subdomains_are_not_profile_hosts(host):
    assert linkedin_url("https://" + host + "/in/fixture-person") == ""


@pytest.mark.parametrize("payload", [{"@type": "Person", "name": "Unlinked Person"}, {"@type": "Person", "url": URL + "-other"}, {"@type": "Organization", "url": URL}])
def test_rejects_unassociated_person(payload):
    assert parse_public_profile(html(payload), URL) is None


def test_no_metadata_or_inline_js_fallback():
    assert parse_public_profile('<meta property="og:title" content="Wrong Person"><script>window.name="Wrong"</script>', URL) is None


def test_disabled_and_no_established_identity_do_not_fetch(monkeypatch):
    monkeypatch.setattr("modules.email_linkedin_public.requests.Session", lambda: pytest.fail("No network authorized"))
    monkeypatch.delenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", raising=False)
    original = established()
    assert enrich_linkedin_public(original)["sources"][-1]["status"] == "disabled"
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    original["profiles"][0]["basis"] = "inferred_username"
    assert enrich_linkedin_public(original)["sources"][-1]["status"] == "unknown"


def test_public_data_appended_without_overwriting_positive(monkeypatch):
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    policy, response = Reply("User-agent: *\nAllow: /"), Reply(html())
    session = Session([policy, response])
    monkeypatch.setattr("modules.email_linkedin_public.requests.Session", lambda: session)
    original = established()
    result = enrich_linkedin_public(original)
    assert session.calls == ["https://www.linkedin.com/robots.txt", URL]
    assert policy.closed and response.closed
    assert len(result["profiles"]) == 2 and result["profiles"][0]["display_name"] == "Original positive"
    assert result["sources"][-1]["status"] == "found"


def test_robots_denial_stops_profile_fetch(monkeypatch):
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    session = Session([Reply("User-agent: *\nDisallow: /in/")])
    monkeypatch.setattr("modules.email_linkedin_public.requests.Session", lambda: session)
    result = enrich_linkedin_public(established())
    assert len(session.calls) == 1 and len(result["profiles"]) == 1
    assert result["sources"][-1]["status"] == "blocked"


@pytest.mark.parametrize("response,expected", [(Reply("Login", 302), "unavailable"), (Reply("Blocked", 999), "blocked"), (Reply("Rate limited", 429), "rate_limited"), (Reply("Login wall"), "unavailable"), (Reply(html(), content_type="application/json"), "unavailable")])
def test_errors_preserve_existing_positives(monkeypatch, response, expected):
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    session = Session([Reply("User-agent: *\nAllow: /"), response])
    monkeypatch.setattr("modules.email_linkedin_public.requests.Session", lambda: session)
    result = enrich_linkedin_public(established())
    assert len(result["profiles"]) == 1 and result["sources"][-1]["status"] == expected
    assert response.closed


def test_size_and_elapsed_bounds():
    with pytest.raises(ValueError):
        bounded_text(Reply("x" * 50), float("inf"), limit=30)
    with pytest.raises(ValueError):
        bounded_text(Reply("x"), -1)


def test_no_credentials_or_error_body_forwarded(monkeypatch):
    import requests
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    session = Session([requests.ConnectionError("PRIVATE COOKIE AND TOKEN")])
    monkeypatch.setattr("modules.email_linkedin_public.requests.Session", lambda: session)
    result = enrich_linkedin_public(established())
    assert result["sources"][-1]["status"] == "unavailable"
    assert "PRIVATE" not in str(result)


@pytest.mark.parametrize("historical", [False, True])
def test_github_explicit_link_preserves_association_basis(monkeypatch, historical):
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    session = Session([Reply("User-agent: *\nDisallow: /in/")])
    monkeypatch.setattr("modules.email_linkedin_public.requests.Session", lambda: session)
    github = {"status": "found", "profile_status": "ok", "website": URL, "url": "https://github.com/fixture", "evidence": "Exact email published on this GitHub profile"}
    if historical:
        github.update(evidence="Historical public commit", evidence_url="https://github.com/fixture/repo/commit/fixture", commit_date="2020-01-01")
    result = enrich_public_linkedin({"profiles": [], "sources": []}, github=github)
    assert len(result["profiles"]) == 1
    assert result["profiles"][0]["basis"] == ("historical_public_link" if historical else "public_link")
    assert result["sources"][-1]["status"] == "blocked"


def test_github_found_without_explicit_association_cannot_supply_link(monkeypatch):
    monkeypatch.setenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "true")
    monkeypatch.setattr("modules.email_linkedin_public.requests.Session", lambda: pytest.fail("No established URL"))
    result = enrich_public_linkedin({"profiles": [], "sources": []}, github={"status": "found", "profile_status": "ok", "website": URL})
    assert result["profiles"] == [] and result["sources"][-1]["status"] == "unknown"
