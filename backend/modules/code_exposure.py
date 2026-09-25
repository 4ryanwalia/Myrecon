"""
Commit-email exposure, the address a developer publishes without meaning to.

`git config user.email` ends up inside every commit object, and GitHub serves
those commits through a public, unauthenticated API. Most developers have no
idea their personal address is readable by anyone who asks; it is one of the
few findings in this tool that is genuinely news to the person it is about,
which is why it belongs in a self-exposure report rather than buried in a
profile card.

It also pays for itself downstream: an address discovered here feeds straight
into the existing email pipeline, breach lookup, Gravatar, and the account
correlation that hangs off both, so one finding turns into several.

Not via the events feed, which is where this technique is usually documented:
GitHub has since stripped commit details out of it, and a PushEvent payload
now carries only `repository_id`, `push_id`, `ref`, `head` and `before`. The
commits API still returns full author metadata, so the route is
repos → commits, filtered by `author=` so we collect the target's own
addresses and not those of everyone who ever contributed to their projects.

Limits, surfaced rather than hidden:
  * Forks are skipped, their history is somebody else's commits.
  * Costs 1 + `max_repos` API calls. Unauthenticated is 60/hour per IP;
    `GITHUB_TOKEN` raises it to 5000 and needs no scope.
"""

import os
import re
import threading
import time

import requests

from core.cache import TTLCache

API = "https://api.github.com"

# GitHub's own privacy-preserving address. Finding one means the user already
# turned the protection on, so it is the opposite of an exposure.
_NOREPLY = "users.noreply.github.com"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_TIMEOUT = 12
_MAX_REPOS = 5
_COMMITS_PER_REPO = 30

# A finished answer for a handle is reused for six hours: commit history does
# not change between two scans of the same person, and every repeat costs six
# calls out of a 60/hour budget that the whole server shares. Errors are never
# cached, so a failed look is retried on the next scan.
_RESULTS = TTLCache(ttl=6 * 3600, max_entries=500)

# Once GitHub says the budget is spent, remember when it refills and stop
# asking until then. Without this every scan in that hour made one more
# doomed call and printed the same failure.
_limit_lock = threading.Lock()
_limited_until = 0.0


def _note_limit(resp) -> None:
    global _limited_until
    try:
        reset = float(resp.headers.get("X-RateLimit-Reset", "0"))
    except ValueError:
        reset = 0.0
    with _limit_lock:
        _limited_until = max(_limited_until, reset or time.time() + 900)


def _limit_error():
    with _limit_lock:
        until = _limited_until
    if until <= time.time():
        return None
    return {"error": "GitHub's hourly lookup limit is used up",
            "limited": True, "retry_at": int(until), "emails": []}


def _headers() -> dict:
    headers = {
        "User-Agent": "MyRecon/1.0 (+https://myrecon.xyz)",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _rate_limited(resp) -> bool:
    return resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0"


def github_commit_emails(username: str, max_repos: int = _MAX_REPOS,
                         timeout: int = _TIMEOUT) -> dict:
    """
    Addresses `username` has published through public commit metadata.

    Returns ``{"emails": [...], "repos_checked": n, "commits_seen": n,
    "protected": bool}``. An empty ``emails`` list with ``protected`` set means
    every commit used GitHub's noreply address, worth reporting as a *good*
    result rather than as silence. ``{"error": ...}`` covers rate limiting and
    missing users, so the caller can tell "nothing found" from "we could not
    look".
    """
    if not username:
        return {"emails": [], "repos_checked": 0, "commits_seen": 0, "protected": False}

    key = f"{username.lower()}|{max_repos}"
    cached = _RESULTS.get(key)
    if cached is not None:
        return cached
    limited = _limit_error()
    if limited:
        return limited

    result = _lookup(username, max_repos, timeout)
    if "error" not in result:
        _RESULTS.set(key, result)
    return result


def _lookup(username: str, max_repos: int, timeout: int) -> dict:
    headers = _headers()
    try:
        resp = requests.get(
            f"{API}/users/{username}/repos",
            params={"per_page": 30, "sort": "pushed", "type": "owner"},
            headers=headers, timeout=timeout,
        )
    except requests.RequestException as e:
        return {"error": f"request failed: {type(e).__name__}", "emails": []}

    if resp.status_code == 404:
        return {"error": "no such GitHub user", "emails": []}
    if _rate_limited(resp):
        _note_limit(resp)
        return _limit_error() or {"error": "GitHub's hourly lookup limit is used up",
                                  "limited": True, "emails": []}
    if resp.status_code != 200:
        return {"error": f"GitHub returned {resp.status_code}", "emails": []}

    try:
        repos = [r for r in resp.json() if not r.get("fork")][:max_repos]
    except ValueError:
        return {"error": "unreadable response from GitHub", "emails": []}

    found: dict = {}
    noreply_seen = False
    commits_seen = 0
    checked = 0

    for repo in repos:
        full_name = repo.get("full_name")
        if not full_name:
            continue
        try:
            cresp = requests.get(
                f"{API}/repos/{full_name}/commits",
                # author= keeps this to the target's own commits rather than
                # harvesting every contributor's address.
                params={"author": username, "per_page": _COMMITS_PER_REPO},
                headers=headers, timeout=timeout,
            )
        except requests.RequestException:
            continue
        if _rate_limited(cresp):
            _note_limit(cresp)
            break
        if cresp.status_code != 200:
            continue
        checked += 1
        try:
            commits = cresp.json()
        except ValueError:
            continue
        if not isinstance(commits, list):
            continue

        for commit in commits:
            author = ((commit.get("commit") or {}).get("author")) or {}
            email = (author.get("email") or "").strip().lower()
            commits_seen += 1
            if not email or not _EMAIL_RE.match(email):
                continue
            if email.endswith(_NOREPLY):
                noreply_seen = True
                continue
            entry = found.setdefault(
                email,
                {"email": email, "name": author.get("name", ""), "commits": 0, "repos": []},
            )
            entry["commits"] += 1
            if full_name not in entry["repos"]:
                entry["repos"].append(full_name)

    emails = sorted(found.values(), key=lambda e: -e["commits"])
    return {
        "emails": emails,
        "repos_checked": checked,
        "commits_seen": commits_seen,
        "protected": bool(noreply_seen and not emails),
    }
