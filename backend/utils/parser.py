"""
╔══════════════════════════════════════════════════════════════╗
║  Result Parser — Categorisation, Deduplication, Export      ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
from datetime import datetime
from typing import Any

from data.profile_urls import handles_match, profile_handle


# ──────────────────────────────────────────────────────────────
#  Category detection patterns
# ──────────────────────────────────────────────────────────────

DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".csv", ".txt", ".rtf", ".odt", ".xml", ".json", ".yml",
    ".yaml", ".sql", ".log", ".env", ".conf", ".cfg", ".ini",
}


def categorise_result(result: dict, target: str = "") -> str:
    """
    Classify a result as 'profile', 'document', or 'mention'.

    'profile' is a claim that the URL is somebody's account page, so it is
    only made when the URL is *shaped* like one — github.com/<handle>, not
    any github.com page that mentions the handle — and, when `target` names
    the handle we searched for, when the URL's own handle is that one.
    Everything else on those domains is a mention: still a finding, still
    shown, but not sold to the user as an account that exists.

    Search results are indexed pages, and the index goes stale; callers that
    report profiles as *found* verify them over HTTP first.
    """
    url = result.get("url", "")
    lowered = url.lower()

    # Check document extensions
    for ext in DOCUMENT_EXTENSIONS:
        if lowered.endswith(ext):
            return "document"

    # Check filetype dorks
    query = result.get("query", "").lower()
    if "filetype:" in query:
        return "document"

    # Already verified upstream by an HTTP check against a known profile URL.
    source = result.get("source", "")
    if source in ("username_check", "email_lookup"):
        return "profile"

    match = profile_handle(url)
    if not match:
        return "mention"
    _domain, handle = match
    if target and not handles_match(handle, target):
        # Profile-shaped, but it is somebody else's profile.
        return "mention"
    return "profile"


def deduplicate_results(results: list[dict]) -> list[dict]:
    """Remove duplicate results based on URL."""
    seen = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if not url:
            # Keep non-URL results (like HIBP)
            unique.append(r)
            continue
        if url not in seen:
            seen.add(url)
            unique.append(r)
    return unique


def categorise_all(results: list[dict], target: str = "") -> dict[str, list[dict]]:
    """Categorise and group results into profiles, documents, mentions."""
    categorised = {
        "profiles": [],
        "documents": [],
        "mentions": [],
    }

    for result in results:
        cat = categorise_result(result, target)
        result["category"] = cat
        if cat == "profile":
            categorised["profiles"].append(result)
        elif cat == "document":
            categorised["documents"].append(result)
        else:
            categorised["mentions"].append(result)

    return categorised


def build_report(
    username: str,
    email: str,
    results: list[dict],
    scan_mode: str = "fast",
) -> dict[str, Any]:
    """Build a structured JSON report from scan results."""
    unique = deduplicate_results(results)
    categorised = categorise_all(unique, username)

    report = {
        "meta": {
            "tool": "RECON OSINT Scanner",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "target_username": username,
            "target_email": email,
            "scan_mode": scan_mode,
            "total_results": len(unique),
        },
        "summary": {
            "profiles_found": len(categorised["profiles"]),
            "documents_found": len(categorised["documents"]),
            "mentions_found": len(categorised["mentions"]),
        },
        "results": categorised,
    }

    return report


def export_json(report: dict, filepath: str) -> str:
    """Export the report to a JSON file and return the path."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return filepath


def extract_urls(results: list[dict]) -> list[str]:
    """Extract clean unique URLs from results."""
    urls = set()
    for r in results:
        url = r.get("url", "")
        if url and url.startswith("http"):
            urls.add(url)
    return sorted(urls)
