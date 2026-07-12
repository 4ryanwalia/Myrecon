"""
╔══════════════════════════════════════════════════════════════╗
║  Result Parser — Categorisation, Deduplication, Export      ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import re
from datetime import datetime
from typing import Any


# ──────────────────────────────────────────────────────────────
#  Category detection patterns
# ──────────────────────────────────────────────────────────────

PROFILE_DOMAINS = {
    "twitter.com", "x.com", "instagram.com", "facebook.com", "tiktok.com",
    "linkedin.com", "github.com", "gitlab.com", "reddit.com", "youtube.com",
    "twitch.tv", "medium.com", "dev.to", "behance.net", "dribbble.com",
    "pinterest.com", "tumblr.com", "snapchat.com", "vk.com", "flickr.com",
    "soundcloud.com", "spotify.com", "steamcommunity.com", "chess.com",
    "about.me", "keybase.io", "mastodon.social", "stackoverflow.com",
    "quora.com", "hackerrank.com", "leetcode.com", "kaggle.com",
    "bitbucket.org", "codepen.io", "500px.com", "deviantart.com",
    "artstation.com", "gravatar.com", "patreon.com", "substack.com",
    "threads.net", "bluesky.social", "kick.com", "odysee.com",
    "buymeacoffee.com", "ko-fi.com", "linktree", "linktr.ee",
}

DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".csv", ".txt", ".rtf", ".odt", ".xml", ".json", ".yml",
    ".yaml", ".sql", ".log", ".env", ".conf", ".cfg", ".ini",
}


def categorise_result(result: dict) -> str:
    """Classify a result as 'profile', 'document', or 'mention'."""
    url = result.get("url", "").lower()

    # Check document extensions
    for ext in DOCUMENT_EXTENSIONS:
        if url.endswith(ext):
            return "document"

    # Check filetype dorks
    query = result.get("query", "").lower()
    if "filetype:" in query:
        return "document"

    # Check profile domains
    for domain in PROFILE_DOMAINS:
        if domain in url:
            return "profile"

    # Source-based classification
    source = result.get("source", "")
    if source == "username_check":
        return "profile"
    if source == "email_lookup":
        return "profile"

    return "mention"


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


def categorise_all(results: list[dict]) -> dict[str, list[dict]]:
    """Categorise and group results into profiles, documents, mentions."""
    categorised = {
        "profiles": [],
        "documents": [],
        "mentions": [],
    }

    for result in results:
        cat = categorise_result(result)
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
    categorised = categorise_all(unique)

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
