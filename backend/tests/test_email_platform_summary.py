"""Distinct-platform counts retain association scope and incomplete coverage."""
import pytest

from modules.email_platform_summary import build_platform_summary, canonical_platform
from services.email import _merge_enrichment_links


def profile(platform, basis="provider_email", **extra):
    return {"platform": platform, "basis": basis, "source": "Fixture provider", **extra}


def summarize(profiles=(), **extra):
    return build_platform_summary({"account_checks": {"enabled": True},
                                   "evidence_report": {"profiles": list(profiles)}, **extra})


@pytest.mark.parametrize("name,ident", [("Google Maps", "google"), ("gmail.com", "google"),
                                      ("YouTube", "google"), ("X.com", "twitter"),
                                      ("Twitter", "twitter"), ("www.linkedin.com", "linkedin")])
def test_known_platform_aliases_share_identifiers(name, ident):
    assert canonical_platform(name)[0] == ident


def test_multiple_profile_rows_registration_and_history_do_not_inflate_platform_count():
    result = summarize([profile("Google Maps"), profile("Gmail"), profile("YouTube"),
                        profile("X"), profile("Twitter.com")],
                       registration_checks={"status": "ok", "services": [
                           {"service": "Twitter", "domain": "twitter.com", "status": "found"},
                           {"service": "Spotify", "domain": "spotify.com", "status": "found"}]},
                       breaches={"sources": [{"name": "Twitter.com"}, {"name": "Canva.com"}]})
    assert result["counts"] == {"total_platforms": 4, "linked_platforms": 3,
                               "public_profile_platforms": 2, "registration_platforms": 2,
                               "historical_platforms": 2, "historical_only_platforms": 1,
                               "owner_declared_platforms": 0}
    twitter = next(row for row in result["platforms"] if row["id"] == "twitter")
    assert twitter["linked"] and twitter["historical"]
    assert set(twitter["kinds"]) == {"profile", "registration", "breach"}


def test_historical_owner_declared_and_auxiliary_evidence_are_not_current_links():
    result = summarize([profile("GitHub", "historical_commit"),
                        profile("LinkedIn", "historical_public_link"), profile("Instagram", "public_link")],
                       linked_services={"services": [{"service": "OpenPGP key", "kind": "profile"},
                                                     {"service": "Canva", "kind": "breach"},
                                                     {"service": "Pinterest", "kind": "profile", "basis": "owner_declared"}]})
    assert result["counts"]["linked_platforms"] == 0
    assert result["counts"]["total_platforms"] == 5
    assert result["counts"]["historical_only_platforms"] == 3
    assert result["counts"]["owner_declared_platforms"] == 3
    assert all(row["id"] != "openpgpkey" for row in result["platforms"])


def test_independent_nonhistorical_provenance_coexists_with_primary_historical_basis():
    result = summarize([profile("GitHub", "historical_commit", provenance=[
        {"basis": "historical_commit", "source": "GitHub public API"},
        {"basis": "provider_email", "source": "Fixture provider"}])])
    row = result["platforms"][0]
    assert set(row["basis"]) == {"historical_commit", "provider_email"}
    assert row["linked"] and row["historical"] and not row["historical_only"]
    assert result["counts"]["linked_platforms"] == result["counts"]["historical_platforms"] == 1


def test_no_registration_signal_and_a_failed_source_remain_unknown():
    result = summarize(account_checks={"enabled": True, "sources": [{"name": "GitHub", "status": "no_match"}]},
                       profile_enrichment={"sources": [{"name": "GitHub", "status": "rate_limited"}]},
                       registration_checks={"status": "unavailable", "services": [
                           {"service": "Spotify", "status": "no_signal"},
                           {"service": "Pinterest", "status": "timeout"},
                           {"service": "Adobe", "status": "skipped"}]})
    assert result["counts"]["total_platforms"] == 0
    assert result["status"] == "unavailable"
    assert result["coverage"]["unknown"] == 3
    assert result["coverage"]["not_found"] == 0
    assert result["coverage"]["skipped"] == 1
    assert result["coverage"]["attempted"] == 3
    assert next(row for row in result["platforms"] if row["id"] == "github")["status"] == "unknown"


def test_direct_no_match_is_scoped_to_source_coverage_not_universal_account_absence():
    result = summarize(account_checks={"enabled": True, "sources": [{"name": "GitHub", "status": "no_match"},
                                                                      {"name": "Gravatar", "status": "skipped"}]})
    assert result["coverage"]["not_found"] == result["coverage"]["checked"] == 1
    assert result["coverage"]["skipped"] == 1
    assert result["counts"]["linked_platforms"] == 0
    assert "does not prove no account" in result["note"]


def test_review_provider_failure_does_not_relabel_account_platform_coverage():
    result = summarize([profile("Google")], profile_enrichment={"sources": [
        {"name": "Google Maps public reviews", "provider": "SerpApi", "status": "unavailable"}]})
    assert result["status"] == "ok"
    assert result["coverage"]["unknown"] == 0
    assert result["coverage"]["sources"][0]["scope"] == "reviews"
    assert result["counts"]["linked_platforms"] == 1


def test_compilations_never_become_platform_associations():
    result = summarize(breaches={"sources": [{"name": "Collection 1"}, {"name": "Stealer Logs"},
                                             {"name": "Canva"}]})
    assert result["counts"]["historical_platforms"] == 1
    assert [row["name"] for row in result["platforms"]] == ["Canva"]


def test_disabled_optional_checks_preserve_historical_findings_and_explicit_scope():
    result = summarize(account_checks={"enabled": False}, breaches={"sources": [{"name": "Canva"}]})
    assert result["status"] == "skipped" and result["enabled"] is False
    assert result["counts"]["historical_platforms"] == 1
    assert result["counts"]["linked_platforms"] == 0


def test_provider_profile_upgrades_primary_breach_kind_without_losing_history():
    result = {"linked_services": {"services": [{"service": "LinkedIn.com", "kind": "breach",
                                                 "date": "2012", "evidence": "Historical breach"}]},
              "profile_enrichment": {"profiles": [profile("LinkedIn", url="https://linkedin.com/in/fixture")], "registrations": []},
              "breach_details": {"records": []}}
    _merge_enrichment_links(result)
    row = result["linked_services"]["services"][0]
    assert row["kind"] == "profile" and row["basis"] == "provider_email"
    assert row["historical_evidence"][0]["date"] == "2012"
    summary = summarize(**result)
    assert summary["counts"]["linked_platforms"] == summary["counts"]["historical_platforms"] == 1
    assert summary["counts"]["historical_only_platforms"] == 0


def test_profile_upgrade_preserves_positive_registration_signal():
    result = {"linked_services": {"services": [{"service": "Google", "kind": "registration", "evidence": "Registration signal"}]},
              "profile_enrichment": {"profiles": [profile("Google Maps")], "registrations": []},
              "breach_details": {"records": []}}
    _merge_enrichment_links(result)
    row = result["linked_services"]["services"][0]
    assert row["kind"] == "profile" and row["registration_status"] == "found"
    assert row["registration_evidence"] == "Registration signal"
    assert summarize(**result)["counts"]["registration_platforms"] == 1


@pytest.mark.parametrize("reverse", [False, True])
def test_existing_alias_rows_preserve_profile_and_registration_evidence(reverse):
    services = [{"service": "Google", "kind": "profile", "basis": "provider_email"},
                {"service": "YouTube", "kind": "registration", "evidence": "Registration signal"}]
    result = {"linked_services": {"services": list(reversed(services)) if reverse else services},
              "profile_enrichment": {"profiles": [], "registrations": []}, "breach_details": {"records": []}}
    _merge_enrichment_links(result)
    row = result["linked_services"]["services"][0]
    assert row["kind"] == "profile" and row["registration_status"] == "found"
    assert result["linked_services"]["from_registration"] == 1
    assert summarize(**result)["counts"]["registration_platforms"] == 1


def test_service_projects_summary_after_evidence_and_retains_partial_findings(monkeypatch):
    from services import email as service
    monkeypatch.setattr(service.EmailLookup, "scan", lambda *a, **kw: {
        "github": {"status": "found", "username": "fixture", "url": "https://github.com/fixture"},
        "summary": {}, "breaches": {"sources": [{"name": "GitHub"}]}})
    monkeypatch.setattr(service, "enrich_email", lambda email: {"status": "unavailable", "profiles": [], "registrations": [], "sources": []})
    monkeypatch.setattr(service, "breach_details", lambda email: {"status": "unconfigured", "records": []})
    monkeypatch.setattr(service, "enrich_linkedin_public", lambda *args: None)
    result = service.scan_email("fixture@example.com", True)
    assert result["platform_summary"]["enabled"] is True
    assert result["platform_summary"]["status"] == "partial"
    assert result["platform_summary"]["counts"]["linked_platforms"] == 1
    assert result["platform_summary"]["counts"]["historical_platforms"] == 1
    assert result["summary"]["linked_platforms_count"] == 1
    assert result["partial"] is True
