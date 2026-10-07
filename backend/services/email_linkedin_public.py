"""Bounded free LinkedIn public details from independently established links.

The email is never converted to a guessed handle. Two public identity sources
run in isolated, time-limited workers; only exact-email GitHub evidence or
email-hash Gravatar owner links can seed the robots-respecting LinkedIn reader.
No paid enrichment, Google session, registration check or account store is used.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

if __name__ == "__main__":
    # -I deliberately omits the script directory from sys.path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.email_linkedin_public import bounded_text, enrich_linkedin_public, linkedin_url


_SLOT = threading.BoundedSemaphore(1)
_STATES = {"ok", "found", "partial", "unknown", "no_match", "disabled", "unconfigured",
           "unavailable", "blocked", "authentication_required", "rate_limited", "timeout"}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BASES = {"exact_public_email", "historical_public_link", "email_hash"}
_DETAIL_REASONS = {
    "found": "Public LinkedIn profile details retrieved.",
    "ok": "Public LinkedIn profile details retrieved.",
    "unknown": "No publicly established LinkedIn profile link was found; this does not establish absence.",
    "disabled": "The public LinkedIn reader is disabled on this backend.",
    "blocked": "LinkedIn excludes or blocks public reading of this profile.",
    "authentication_required": "LinkedIn requires account authorization to display these details.",
    "rate_limited": "The public source is busy or rate limited; try again later.",
    "timeout": "The public source exceeded its lookup time budget.",
    "unavailable": "Public LinkedIn career details could not be retrieved; the linked profile is retained.",
    "partial": "Some public LinkedIn sources could not complete.",
    "no_match": "The public identity source returned no match; this does not establish absence on LinkedIn.",
    "unconfigured": "The public LinkedIn source requires backend configuration.",
}


def _text(value, limit=1000):
    return _CONTROL.sub("", value[:limit]).strip() if isinstance(value, str) else ""


def _state(value):
    return value if isinstance(value, str) and value in _STATES else "unavailable"


def _evidence_url(value):
    try:
        parts = urlsplit(value)
        if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
            return ""
        if parts.hostname == "github.com" and re.fullmatch(r"/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+/commit/[A-Za-z0-9_-]+)?/?", parts.path):
            return "https://github.com" + parts.path.rstrip("/")
        if parts.hostname in ("en.gravatar.com", "gravatar.com", "www.gravatar.com") and re.fullmatch(r"/[a-f0-9]{32}(?:\.json)?/?", parts.path):
            return "https://" + parts.hostname + parts.path.rstrip("/")
    except (ValueError, TypeError, AttributeError):
        pass
    return ""


def _seed(link, basis, evidence_url):
    if not isinstance(link, str):
        return None
    link = linkedin_url(link)
    if not link or basis not in _BASES:
        return None
    reason = {
        "email_hash": "LinkedIn URL declared on the public Gravatar profile derived from the exact email hash; LinkedIn email ownership is not independently verified.",
        "exact_public_email": "LinkedIn URL declared on a GitHub profile publishing the exact email; LinkedIn email ownership is not independently verified.",
        "historical_public_link": "LinkedIn URL declared on a GitHub profile associated with an exact historical commit email; current email ownership is unknown.",
    }[basis]
    return {"platform": "LinkedIn", "url": link, "username": link.rsplit("/", 1)[-1],
            "source": "Gravatar public profile link" if basis == "email_hash" else "GitHub public profile link",
            "basis": basis, "profile_status": "ok", "evidence": reason,
            "evidence_url": _evidence_url(evidence_url), "fields": {}, "positions": [], "education": [], "current_work": []}


def _github_links(data, social_accounts=None):
    data = data if isinstance(data, dict) else {}
    status = _state(data.get("status"))
    result = {"status": status, "links": []}
    if status != "found" or data.get("profile_status") != "ok":
        return result
    if data.get("evidence") == "Exact email published on this GitHub profile":
        basis, evidence = "exact_public_email", data.get("url", "")
    elif data.get("evidence_url") and re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}", str(data.get("commit_date", ""))):
        basis, evidence = "historical_public_link", data["evidence_url"]
    else:
        return result
    evidence = _evidence_url(evidence)
    if not evidence:
        return result
    urls = [data.get("website")]
    # An explicit URL on an email-associated public bio is a declared link;
    # display-name matches and local-part guesses are never considered.
    bio = data.get("bio") if isinstance(data.get("bio"), str) else ""
    urls.extend(re.findall(r"https://[^\s\"'<>\)\]]+", bio[:2000]))
    for account in social_accounts[:30] if isinstance(social_accounts, list) else []:
        if isinstance(account, dict):
            urls.append(account.get("url"))
    for url in urls:
        if isinstance(url, str):
            url = url.rstrip(".,;:!?")
        candidate = _seed(url, basis, evidence)
        if candidate and all(previous["url"] != candidate["url"] for previous in result["links"]):
            result["links"].append(candidate)
    result["links"] = result["links"][:2]
    return result


def _github_social_accounts(data, deadline):
    """One anonymous read for an already email-associated GitHub username."""
    import requests
    username = data.get("username") if isinstance(data, dict) else ""
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", username):
        return {"status": "unknown", "accounts": []}
    if _evidence_url(data.get("url")) != "https://github.com/" + username:
        return {"status": "unknown", "accounts": []}
    # Reserve the full connect/read budget before starting. Slow author lookup
    # cannot cause a social request to discard already-established links when
    # the outer worker reaches its 25-second limit.
    if time.monotonic() + 8 >= deadline:
        return {"status": "timeout", "accounts": []}
    response = None
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get("https://api.github.com/users/" + username + "/social_accounts",
                                   headers={"User-Agent": "MyReconPublicProfile/1.0", "Accept": "application/vnd.github+json",
                                            "X-GitHub-Api-Version": "2022-11-28"},
                                   params={"per_page": 30}, timeout=(3, 5), allow_redirects=False, stream=True)
            if response.status_code != 200:
                return {"status": "rate_limited" if response.status_code in (403, 429) else "unavailable", "accounts": []}
            # Leave one socket-read interval to finish after the streaming
            # deadline check and still return before the outer worker limit.
            accounts = json.loads(bounded_text(response, deadline - 5, 100_000))
            if not isinstance(accounts, list):
                return {"status": "unknown", "accounts": []}
            return {"status": "ok", "accounts": [{"url": _text(row.get("url"), 3000)} for row in accounts[:30] if isinstance(row, dict)]}
    except (requests.Timeout, TimeoutError):
        return {"status": "timeout", "accounts": []}
    except (requests.RequestException, ValueError, TypeError, AttributeError, RecursionError):
        return {"status": "unavailable", "accounts": []}
    finally:
        if response is not None:
            response.close()


def _github_discovery(email):
    from modules.email_lookup import EmailLookup
    deadline = time.monotonic() + 23
    data = EmailLookup().github(email)
    result = _github_links(data)
    # Require the adapter's explicit author-email association before any social
    # lookup, even when its public website/bio contains no LinkedIn link.
    established = (isinstance(data, dict) and data.get("status") == "found" and data.get("profile_status") == "ok" and
                   (data.get("evidence") == "Exact email published on this GitHub profile" or
                    (data.get("evidence_url") and re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}", str(data.get("commit_date", ""))))))
    if not established:
        return result
    socials = _github_social_accounts(data, deadline)
    if socials["status"] == "ok":
        result = _github_links(data, socials["accounts"])
    result["social_status"] = socials["status"]
    return result


def _gravatar_links(email):
    import requests
    digest = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    endpoint = f"https://en.gravatar.com/{digest}.json"
    response = None
    try:
        deadline = time.monotonic() + 10
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(endpoint, headers={"User-Agent": "MyReconPublicProfile/1.0", "Accept": "application/json"},
                                   timeout=(3, 5), allow_redirects=False, stream=True)
            if response.status_code != 200:
                return {"status": {404: "no_match", 429: "rate_limited"}.get(response.status_code, "unavailable"), "links": []}
            data = json.loads(bounded_text(response, deadline))
            entries = data.get("entry") if isinstance(data, dict) else None
            entry = entries[0] if isinstance(entries, list) and entries and isinstance(entries[0], dict) else None
            if not entry:
                return {"status": "unknown", "links": []}
            links = []
            for key in ("accounts", "verifiedAccounts", "urls"):
                rows = entry.get(key) if isinstance(entry.get(key), list) else []
                for row in rows[:30]:
                    if not isinstance(row, dict):
                        continue
                    candidate = _seed(row.get("url", row.get("value")), "email_hash", endpoint)
                    if candidate and all(previous["url"] != candidate["url"] for previous in links):
                        links.append(candidate)
            return {"status": "found", "links": links[:2]}
    except (requests.Timeout, TimeoutError):
        return {"status": "timeout", "links": []}
    except (requests.RequestException, ValueError, TypeError, AttributeError, RecursionError):
        return {"status": "unavailable", "links": []}
    finally:
        if response is not None:
            response.close()


def _discover_source(email, provider):
    """Kill slow legacy GitHub fanout while retaining the other source's result."""
    timeout = 25 if provider == "GitHub" else 12
    try:
        with tempfile.TemporaryDirectory(prefix="myrecon-linkedin-") as directory:
            output = Path(directory) / "public.json"
            env = {key: value for key, value in os.environ.items()
                   if not any(word in key.upper() for word in ("TOKEN", "API_KEY", "APIKEY", "PASSWORD", "SECRET", "COOKIE", "CREDENTIAL", "SESSION", "SERVICE_ACCOUNT"))}
            completed = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--discovery-worker", provider, str(output)],
                                       input=json.dumps({"email": email}), text=True, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=timeout, shell=False, cwd=directory, env=env)
            if completed.returncode != 0 or not output.is_file():
                raise ValueError("Discovery worker failed")
            with output.open("rb") as handle:
                raw = handle.read(100_001)
            if len(raw) > 100_000:
                raise ValueError("Discovery response exceeded bounds")
            result = json.loads(raw)
            if not isinstance(result, dict) or not isinstance(result.get("links"), list):
                raise ValueError("Invalid discovery projection")
            return result
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "links": []}
    except (OSError, ValueError, TypeError):
        return {"status": "unavailable", "links": []}


def _rows(values, names):
    result = []
    for row in values[:50] if isinstance(values, list) else []:
        if not isinstance(row, dict):
            continue
        projected = {key: _text(row.get(key), 1500 if key == "description" else 300) for key in names}
        projected = {key: value for key, value in projected.items() if value}
        if isinstance(row.get("current"), bool) and "company" in names and "start" in names:
            projected["current"] = row["current"]
        if projected and (projected.get("school") or projected.get("company")):
            result.append(projected)
    return result


def _current_work(values):
    allowed = []
    for row in values[:50] if isinstance(values, list) else []:
        if not isinstance(row, dict) or row.get("current") is False or row.get("isCurrent") is False:
            continue
        end = row.get("end", row.get("endDate", ""))
        end = str(end).strip() if isinstance(end, (str, int, float)) and not isinstance(end, bool) else ""
        if end and end.casefold() not in ("present", "current"):
            continue
        allowed.append(row)
    return _rows(allowed, ("title", "company"))


def _project(seed, details=None, state="unavailable"):
    details = details if isinstance(details, dict) else {}
    state = _state(state)
    fields = details.get("fields") if isinstance(details.get("fields"), dict) else {}
    result = {key: seed[key] for key in ("platform", "url", "username", "source", "basis", "profile_status", "evidence", "evidence_url")}
    for key, limit in (("display_name", 300), ("bio", 3000), ("location", 300)):
        result[key] = _text(details.get(key), limit)
    result["avatar_url"] = ""
    try:
        photo = urlsplit(details.get("avatar_url", ""))
        if photo.scheme == "https" and photo.hostname and photo.hostname.endswith(".licdn.com") and not photo.username and not photo.password and photo.port in (None, 443):
            result["avatar_url"] = _text(details["avatar_url"], 3000)
    except (ValueError, TypeError, AttributeError):
        pass
    result["fields"] = {"Headline": _text(fields["Headline"], 500)} if _text(fields.get("Headline"), 500) else {}
    result["positions"] = _rows(details.get("positions"), ("title", "company", "start", "end"))
    result["education"] = _rows(details.get("education"), ("school", "degree", "field_of_study", "start", "end", "description"))
    result["current_work"] = _current_work(details.get("current_work"))
    if state == "found":
        result["source"] = "LinkedIn public JSON-LD"
    result.update(details_status=state, details_reason=_DETAIL_REASONS[state])
    return result


def _lookup(email):
    if os.getenv("EMAIL_LINKEDIN_PUBLIC_ENABLED", "false").lower() != "true":
        return {"query": {"email": email}, "status": "disabled", "profiles": [], "sources": [
            {"name": "LinkedIn public profile", "provider": "Public JSON-LD", "status": "disabled", "reason": _DETAIL_REASONS["disabled"]}]}
    seeds, sources = {}, []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {provider: pool.submit(_discover_source, email, provider) for provider in ("GitHub", "Gravatar")}
        for provider, future in futures.items():
            try:
                discovery = future.result()
                if not isinstance(discovery, dict):
                    raise ValueError("Invalid source projection")
            except Exception:
                discovery = {"status": "unavailable", "links": []}
            state = _state(discovery.get("status"))
            sources.append({"name": "Email-linked " + provider, "provider": provider, "status": state,
                            "reason": "Public email-associated profile queried; only explicit LinkedIn links are used." if state in ("found", "no_match") else _DETAIL_REASONS[state]})
            if provider == "GitHub" and "social_status" in discovery:
                social_state = _state(discovery["social_status"])
                sources.append({"name": "GitHub public social links", "provider": "GitHub", "status": social_state,
                                "reason": "Public social links of the email-associated GitHub profile queried." if social_state == "ok" else
                                          "GitHub social links could not complete; established website and bio links are retained."})
            for candidate in discovery.get("links", [])[:2] if isinstance(discovery.get("links"), list) else []:
                if not isinstance(candidate, dict):
                    continue
                seed = _seed(candidate.get("url"), candidate.get("basis"), candidate.get("evidence_url"))
                if not seed or not seed["evidence_url"]:
                    continue
                previous = seeds.get(seed["url"])
                if not previous or (previous["basis"] == "historical_public_link" and seed["basis"] != "historical_public_link"):
                    seeds[seed["url"]] = seed
    profiles = []
    for seed in list(seeds.values())[:2]:
        enrichment = {"profiles": [deepcopy(seed)], "sources": []}
        try:
            enriched = enrich_linkedin_public(enrichment)
            metadata = enriched.get("sources", [])[-1] if isinstance(enriched, dict) and enriched.get("sources") else {}
            state = _state(metadata.get("status", "unavailable"))
            details = next((profile for profile in reversed(enriched.get("profiles", []))
                            if isinstance(profile, dict) and profile.get("source") == "LinkedIn public JSON-LD"
                            and profile.get("platform") == "LinkedIn" and profile.get("profile_status") == "ok"
                            and linkedin_url(profile.get("url")) == seed["url"]), None)
            if state == "found" and not details:
                state = "unavailable"
        except Exception:
            state, details = "unavailable", None
        profiles.append(_project(seed, details, state))
        sources.append({"name": "LinkedIn public profile", "provider": "Public JSON-LD", "status": state,
                        "url": seed["url"], "reason": _DETAIL_REASONS[state]})
    if profiles:
        status = "ok" if all(profile["details_status"] == "found" for profile in profiles) and all(source["status"] in ("ok", "found", "no_match") for source in sources) else "partial"
    else:
        status = "unknown" if all(source["status"] in ("ok", "found", "no_match") for source in sources) else next((source["status"] for source in sources if source["status"] not in ("ok", "found", "no_match")), "unavailable")
        sources.append({"name": "LinkedIn public profile", "provider": "Public JSON-LD", "status": "unknown", "reason": _DETAIL_REASONS["unknown"]})
    return {"query": {"email": email}, "status": status, "profiles": profiles, "sources": sources}


def lookup_linkedin_public(email):
    if not _SLOT.acquire(blocking=False):
        return {"query": {"email": email}, "status": "rate_limited", "profiles": [], "sources": [
            {"name": "LinkedIn public profile", "provider": "Public JSON-LD", "status": "rate_limited", "reason": _DETAIL_REASONS["rate_limited"]}]}
    try:
        return _lookup(email)
    finally:
        _SLOT.release()


def _worker(provider, output):
    import contextlib
    data = json.loads(sys.stdin.read(2048))
    email = data.get("email", "")
    try:
        with open(os.devnull, "w") as silent, contextlib.redirect_stdout(silent), contextlib.redirect_stderr(silent):
            if provider == "GitHub":
                result = _github_discovery(email)
            elif provider == "Gravatar":
                result = _gravatar_links(email)
            else:
                result = {"status": "unavailable", "links": []}
    except Exception:
        result = {"status": "unavailable", "links": []}
    Path(output).write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "--discovery-worker":
    _worker(sys.argv[2], sys.argv[3])
