"""
Username / full-name search service.

Pipeline:
  1. Username enumeration across the platform database
  2. Parallel profile enrichment (bio, followers, avatar) for the matches
  3. Optional Google dorking when a Custom Search key is configured
  4. Identity correlation into clusters

Enrichment runs in a bounded thread pool so profile photos and metadata are
fetched without serializing dozens of slow requests.
"""

import os
from concurrent.futures import ThreadPoolExecutor

from modules.username_checker import UsernameChecker
from modules.google_dork import GoogleDorkEngine
from modules.correlator import IdentityCorrelator
from modules.enrichment import ProfileEnricher
from utils.parser import categorise_result

_ENRICH_LIMIT = 18  # cap enrichment fan-out to keep latency predictable


def _has_google() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CX_ID"))


def _strip_binary(results: list[dict]) -> None:
    for r in results:
        r.pop("profile_pic_data", None)


def _enrich_profiles(found: list[dict]) -> None:
    """Enrich the strongest matches in parallel to fetch avatars and bios."""
    targets = [r for r in found if r.get("exists")][:_ENRICH_LIMIT]
    if not targets:
        return
    enricher = ProfileEnricher(delay=0)

    def _run(result):
        try:
            enricher.enrich(result)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_run, targets))


def search_username(username: str, deep: bool = False) -> dict:
    all_results: list[dict] = []

    # ── Username enumeration ─────────────────────────────────────
    try:
        checker = UsernameChecker(max_workers=20 if deep else 12, delay=0)
        found = checker.scan(username, deep=deep)
        for r in found:
            r["category"] = categorise_result(r)
        all_results.extend(found)
    except Exception as e:  # noqa: BLE001 - surface as a soft error
        all_results.append({
            "source": "username_check", "error": True, "platform": "Error",
            "url": "", "title": f"Username check error: {e}",
        })

    # ── Enrichment (avatars, bios, follower counts) ──────────────
    _enrich_profiles(all_results)

    # ── Google dorking (optional) ────────────────────────────────
    if _has_google():
        try:
            dork = GoogleDorkEngine(delay=0.2)
            dork_results = dork.scan_username(username, deep=deep)
            for r in dork_results:
                r["category"] = categorise_result(r)
            all_results.extend(dork_results)
        except Exception:
            pass

    # ── Correlation ──────────────────────────────────────────────
    clusters = []
    try:
        clusters = IdentityCorrelator().correlate(all_results, target_username=username)
        for c in clusters:
            c.pop("profile_pic_data", None)
    except Exception:
        pass

    _strip_binary(all_results)

    profiles = [r for r in all_results if r.get("category") == "profile" and r.get("exists")]
    documents = [r for r in all_results if r.get("category") == "document"]
    mentions = [r for r in all_results if r.get("category") == "mention"]

    return {
        "status": "ok",
        "query": {"username": username, "deep": deep},
        "summary": {
            "total": len(profiles) + len(documents) + len(mentions),
            "profiles": len(profiles),
            "documents": len(documents),
            "mentions": len(mentions),
            "clusters": len(clusters),
        },
        "results": {"profiles": profiles, "documents": documents, "mentions": mentions},
        "identity_clusters": clusters,
    }


def search_fullname(full_name: str, deep: bool = False) -> dict:
    all_results: list[dict] = []

    if not _has_google():
        return {
            "status": "ok",
            "query": {"full_name": full_name, "deep": deep},
            "summary": {"total": 0, "profiles": 0, "documents": 0, "mentions": 0},
            "results": {"profiles": [], "documents": [], "mentions": []},
            "notice": "Full-name search requires a Google Custom Search key on the server.",
        }

    try:
        dork = GoogleDorkEngine(delay=0.2)
        dork_results = dork.scan_username(full_name, deep=deep)
        for r in dork_results:
            r["category"] = categorise_result(r)
        all_results.extend(dork_results)
    except Exception as e:  # noqa: BLE001
        all_results.append({
            "source": "google_dork", "error": True,
            "title": f"Dork error: {e}", "url": "",
        })

    _strip_binary(all_results)
    profiles = [r for r in all_results if r.get("category") == "profile"]
    documents = [r for r in all_results if r.get("category") == "document"]
    mentions = [r for r in all_results if r.get("category") == "mention"]

    return {
        "status": "ok",
        "query": {"full_name": full_name, "deep": deep},
        "summary": {
            "total": len(all_results),
            "profiles": len(profiles),
            "documents": len(documents),
            "mentions": len(mentions),
        },
        "results": {"profiles": profiles, "documents": documents, "mentions": mentions},
    }
