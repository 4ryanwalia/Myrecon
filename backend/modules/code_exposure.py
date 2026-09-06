"""
Commit-email exposure — the address a developer publishes without meaning to.

`git config user.email` ends up inside every commit object, and GitHub serves
those commits through a public, unauthenticated API. Most developers have no
idea their personal address is readable by anyone who asks; it is one of the
few findings in this tool that is genuinely news to the person it is about,
which is why it belongs in a self-exposure report rather than buried in a
profile card.

It also pays for itself downstream: an address discovered here feeds straight
into the existing email pipeline — breach lookup, Gravatar, and the account
correlation that hangs off both — so one finding turns into several.

Not via the events feed, which is where this technique is usually documented:
GitHub has since stripped commit details out of it, and a PushEvent payload
now carries only `repository_id`, `push_id`, `ref`, `head` and `before`. The
commits API still returns full author metadata, so the route is
repos → commits, filtered by `author=` so we collect the target's own
addresses and not those of everyone who ever contributed to their projects.

Limits, surfaced rather than hidden:
  * Forks are skipped — their history is somebody else's commits.
  * Costs 1 + `max_repos` API calls. Unauthenticated is 60/hour per IP;
    `GITHUB_TOKEN` raises it to 5000 and needs no scope.
"""

import os
import re

import requests

API = "https://api.github.com"

# GitHub's own privacy-preserving address. Finding one means the user already
# turned the protection on, so it is the opposite of an exposure.
_NOREPLY = "users.noreply.github.com"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_TIMEOUT = 12
_MAX_REPOS = 5
_COMMITS_PER_REPO = 30


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
    every commit used GitHub's noreply address — worth reporting as a *good*
    result rather than as silence. ``{"error": ...}`` covers rate limiting and
    missing users, so the caller can tell "nothing found" from "we could not
    look".
    """
    if not username:
        return {"emails": [], "repos_checked": 0, "commits_seen": 0, "protected": False}

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
        return {"error": "GitHub rate limit reached (set GITHUB_TOKEN to raise it)",
                "emails": []}
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
