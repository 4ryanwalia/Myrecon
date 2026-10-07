"""Optional public LinkedIn JSON-LD reader for already established profile URLs.

Never resolves an email, invents a slug, sends a login/session, or circumvents
robots, redirects, rate limits or access walls. Public HTML is often unavailable.
"""
import json
import os
import re
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

MAX_BYTES = 1_000_000
USER_AGENT = "MyReconPublicProfile/1.0"
ESTABLISHED_BASES = {"provider_email", "exact_public_email", "historical_commit", "email_hash", "public_link", "historical_public_link"}


def linkedin_url(value):
    """Accept one HTTPS public profile path; canonicalize to a fixed host."""
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        allowed_host = host in ("linkedin.com", "www.linkedin.com") or re.fullmatch(r"[a-z]{2}\.linkedin\.com", host)
        if parts.scheme != "https" or not allowed_host or parts.username or parts.password or parts.port not in (None, 443):
            return ""
        if not re.fullmatch(r"/in/[A-Za-z0-9_-]{1,150}/?", parts.path):
            return ""
        return "https://www.linkedin.com" + parts.path.rstrip("/")
    except (ValueError, TypeError):
        return ""


def bounded_text(response, deadline, limit=MAX_BYTES):
    chunks, size = [], 0
    if time.monotonic() > deadline:
        raise ValueError("Public response exceeded its time bound")
    for chunk in response.iter_content(8192):
        size += len(chunk)
        if size > limit or time.monotonic() > deadline:
            raise ValueError("Public response exceeded its bounds")
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


class LinkedData(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.parts = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.active = dict(attrs).get("type", "").lower().split(";")[0].strip() == "application/ld+json"
            self.parts = []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.active:
            if len(self.documents) < 20:
                try:
                    self.documents.append(json.loads("".join(self.parts)))
                except (ValueError, RecursionError):
                    pass
            self.active = False
            self.parts = []


def _nodes(documents):
    """Only inspect top level and JSON-LD graph objects, bounded independently."""
    queue = list(documents)
    visited = 0
    while queue and visited < 200:
        node = queue.pop(0)
        visited += 1
        if isinstance(node, list):
            queue.extend(node[:100])
        elif isinstance(node, dict):
            yield node
            graph = node.get("@graph")
            if isinstance(graph, (list, dict)):
                queue.append(graph)
            main = node.get("mainEntity")
            if isinstance(main, (list, dict)):
                queue.append(main)


def _kind(node, expected):
    kinds = node.get("@type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    return isinstance(kinds, list) and any(k in (expected, "https://schema.org/" + expected, "http://schema.org/" + expected) for k in kinds)


def _list(value):
    return value[:50] if isinstance(value, list) else [value] if value else []


def _name(value):
    from modules.email_enrichment import text
    return text(value.get("name")) if isinstance(value, dict) else text(value)


def _location(value):
    from modules.email_enrichment import text
    if isinstance(value, dict):
        value = value.get("address", value)
    if isinstance(value, dict):
        # Public region only; omit street/zip even when exposed by JSON-LD.
        return ", ".join(filter(None, [text(value.get("addressLocality")), text(value.get("addressRegion")), _name(value.get("addressCountry"))]))
    return text(value)


def _current(role):
    """An absent end date never establishes that a historical role is current."""
    explicit = None
    for key in ("current", "isCurrent"):
        if isinstance(role.get(key), bool):
            explicit = role[key]
            break
    if explicit is False:
        return False
    end = role.get("endDate")
    end = str(end).strip() if isinstance(end, (str, int, float)) and not isinstance(end, bool) else ""
    if end.casefold() in ("present", "current"):
        return True
    if end:
        # A concrete end date contradicts a current flag. Keep the dated role
        # without promoting it into the separate current-employer collection.
        return None
    return explicit


def parse_public_profile(html, expected_url):
    """Project only an identity-matching Schema.org Person into display fields."""
    from modules.email_enrichment import text, url
    expected_url = linkedin_url(expected_url)
    if not expected_url or not isinstance(html, str) or len(html.encode("utf-8")) > MAX_BYTES:
        return None
    parser = LinkedData()
    parser.feed(html)
    for person in _nodes(parser.documents):
        if not _kind(person, "Person"):
            continue
        links = _list(person.get("url")) + _list(person.get("sameAs")) + _list(person.get("@id"))
        if not any(linkedin_url(link) == expected_url for link in links if isinstance(link, str)):
            continue
        image = person.get("image", "")
        if isinstance(image, dict):
            image = image.get("contentUrl", image.get("url", ""))
        fields = {"Headline": text(person.get("jobTitle"))} if text(person.get("jobTitle")) else {}
        positions, education, current_work = [], [], []
        for role in _list(person.get("worksFor")):
            if not isinstance(role, dict):
                continue
            if _kind(role, "OrganizationRole") or _kind(role, "Role"):
                company = _name(role.get("worksFor"))
                item = {"company": company, "title": text(role.get("roleName")), "start": text(role.get("startDate")), "end": text(role.get("endDate"))}
                current = _current(role)
                if current is not None:
                    item["current"] = current
                if current is True and company:
                    current_work.append({k: v for k, v in {"company": company, "title": text(role.get("roleName"))}.items() if v})
            else:
                item = {"company": _name(role)}
                # Schema.org Person.worksFor names organizations the person
                # works for. Historical Role records require explicit status.
                if item["company"] and any(_kind(role, kind) for kind in ("Organization", "Corporation", "LocalBusiness")):
                    current_work.append({k: v for k, v in {"company": item["company"], "title": text(person.get("jobTitle"))}.items() if v})
            item = {k: v for k, v in item.items() if v or isinstance(v, bool)}
            if item:
                positions.append(item)
        for row in _list(person.get("alumniOf")):
            if isinstance(row, dict) and (_kind(row, "Role") or _kind(row, "OrganizationRole")):
                item = {"school": _name(row.get("alumniOf")), "start": text(row.get("startDate")), "end": text(row.get("endDate")), "description": text(row.get("description")),
                        "degree": _name(row.get("degree", row.get("educationalCredentialAwarded"))), "field_of_study": _name(row.get("fieldOfStudy"))}
            else:
                item = {"school": _name(row)}
                if isinstance(row, dict):
                    item.update(degree=_name(row.get("degree", row.get("educationalCredentialAwarded"))),
                                field_of_study=_name(row.get("fieldOfStudy")), description=text(row.get("description")))
            item = {k: v for k, v in item.items() if v}
            if item:
                education.append(item)
        return {"platform": "LinkedIn", "url": expected_url, "username": expected_url.rsplit("/", 1)[-1],
                "display_name": text(person.get("name")), "bio": text(person.get("description"), 6000),
                "avatar_url": url(image), "location": _location(person.get("homeLocation", person.get("address", ""))),
                "fields": fields, "positions": positions, "education": education, "current_work": current_work,
                "reviews": [], "stats": {}, "lists": {},
                "source": "LinkedIn public JSON-LD", "basis": "public_link", "profile_status": "ok",
                "evidence": "Public structured data matched an already source-established LinkedIn profile URL; does not independently verify its email association."}
    return None


def enrich_public_linkedin(enrichment, github=None):
    """Append public details without overwriting any source-established profile."""
    source = {"name": "LinkedIn public profile", "provider": "Public JSON-LD", "status": "disabled"}
    enrichment.setdefault("sources", []).append(source)
    if os.getenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "false").lower() != "true":
        source["reason"] = "Optional public reader requires EMAIL_LINKEDIN_PUBLIC_ENABLED=true; no API key required."
        return enrichment
    profiles = enrichment.get("profiles", [])
    if isinstance(github, dict) and github.get("status") == "found" and github.get("profile_status") == "ok":
        linked = linkedin_url(github.get("website"))
        historic = bool(github.get("evidence_url") and github.get("commit_date"))
        exact = github.get("evidence") == "Exact email published on this GitHub profile"
        if linked and (historic or exact) and not any(linkedin_url(p.get("url")) == linked for p in profiles if isinstance(p, dict)):
            profiles.append({"platform": "LinkedIn", "url": linked, "username": linked.rsplit("/", 1)[-1],
                             "source": "GitHub public profile link", "basis": "historical_public_link" if historic else "public_link",
                             "profile_status": "ok", "fields": {}, "stats": {}, "lists": {}, "positions": [], "education": [], "reviews": [],
                             "evidence_url": github.get("url", ""),
                             "evidence": "LinkedIn URL explicitly published on an email-associated GitHub profile. " +
                                         ("GitHub association comes from a historical commit; current email ownership is unknown." if historic else "The email is public on the GitHub profile; LinkedIn does not independently verify this email.")})
            enrichment["profiles"] = profiles
    candidate = next((p for p in profiles if isinstance(p, dict) and p.get("platform") == "LinkedIn" and p.get("profile_status") == "ok" and p.get("basis") in ESTABLISHED_BASES and linkedin_url(p.get("url"))), None)
    if candidate is None:
        source.update(status="unknown", reason="No source-established LinkedIn profile URL is available.")
        return enrichment
    target = linkedin_url(candidate["url"])
    response = None
    try:
        deadline = time.monotonic() + 15
        with requests.Session() as session:
            session.trust_env = False
            session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
            response = session.get("https://www.linkedin.com/robots.txt", timeout=(3, 5), allow_redirects=False, stream=True)
            if response.status_code != 200:
                source.update(status="unavailable", reason="Public access policy could not be checked.")
                return enrichment
            policy = RobotFileParser()
            policy.parse(bounded_text(response, deadline, 100_000).splitlines())
            response.close()
            response = None
            if not policy.can_fetch(USER_AGENT, target):
                source.update(status="blocked", reason="LinkedIn robots.txt excludes this public profile path.")
                return enrichment
            session.cookies.clear()
            response = session.get(target, timeout=(3, 5), allow_redirects=False, stream=True)
            if response.status_code != 200:
                source.update(status={401: "authentication_required", 403: "blocked", 429: "rate_limited", 999: "blocked"}.get(response.status_code, "unavailable"), reason="Public profile source did not return readable data.")
                return enrichment
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                raise ValueError("Not HTML")
            profile = parse_public_profile(bounded_text(response, deadline), target)
            if profile:
                if candidate.get("basis") in ("historical_commit", "historical_public_link"):
                    profile["basis"] = "historical_public_link"
                profiles.append(profile)
                source.update(status="found", reason="Public structured profile data retrieved; unavailable fields remain absent.")
            else:
                source.update(status="unavailable", reason="No identity-matching public structured profile was returned; it may be private or behind a login wall.")
    except (requests.RequestException, ValueError, TypeError, AttributeError, RecursionError):
        source.update(status="unavailable", reason="Public profile could not return a verified readable response.")
    finally:
        if response is not None:
            response.close()
    return enrichment


# Retain the descriptive initial name for callers/tests using that entry point.
enrich_linkedin_public = enrich_public_linkedin
