"""Explicit public account URLs, bounded suggestions, and signed follow actions."""
import copy
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from itsdangerous import BadSignature, URLSafeTimedSerializer

import config
from core.netguard import BlockedRequest, _refuse_internal
from core.validation import ValidationError
from modules.deep_search_plan import parse_input

MAX_SUGGESTIONS = 30
MAX_FOLLOWS = 3
_HANDLE = r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}"
_RESERVED = {"login", "logout", "signup", "register", "search", "explore", "settings",
             "about", "help", "privacy", "terms", "home", "intent", "share", "i"}
_RESERVED_ROUTES = {
    "GitHub": {"features", "topics", "collections", "marketplace", "notifications", "organizations", "orgs", "users", "sponsors"},
    "Instagram": {"p", "reel", "reels", "stories", "direct", "accounts", "developer"},
    "Twitter / X": {"messages", "notifications", "compose", "hashtag", "lists", "status"},
    "Facebook": {"watch", "groups", "events", "pages", "photo.php", "profile.php", "reel"},
}
_DATA = Path(__file__).resolve().parents[1] / "data"
_TEMPLATES = []
for filename in ("platforms_full.json", "platforms_extra.json"):
    if (_DATA / filename).exists():
        for platform in json.loads((_DATA / filename).read_text(encoding="utf-8")):
            template = platform["url"].replace("https://www.", "https://")
            if template.count("{username}") != 1:
                continue
            pattern = re.escape(template.rstrip("/")).replace(re.escape("{username}"), "(?P<handle>" + _HANDLE + ")")
            _TEMPLATES.append((platform["name"], template, re.compile(pattern + r"/?", re.I)))
# Alternate account routes already used by public-source adapters.
for name, template in (("Twitter / X", "https://twitter.com/{username}"),
                       ("Reddit", "https://reddit.com/u/{username}"),
                       ("Bluesky", "https://bsky.app/profile/{username}")):
    _TEMPLATES.append((name, template, re.compile(re.escape(template).replace(re.escape("{username}"), "(?P<handle>" + _HANDLE + ")") + r"/?", re.I)))


def account_url(raw, validate_network=True):
    """Reverse only catalogue account routes; never take an arbitrary path segment."""
    if not isinstance(raw, str) or len(raw) > 2048 or any(ord(c) < 32 for c in raw):
        return None
    try:
        p = urlsplit(raw)
        if p.scheme not in ("http", "https") or not p.hostname or p.username is not None or p.password is not None or p.port not in (None, 80, 443):
            return None
        host = p.hostname.lower().removeprefix("www.")
        path = unquote(p.path)
        if re.search(r"[%\\\s]", path):
            return None
        base = urlunsplit(("https", host, path, "", ""))
        for name, template, pattern in _TEMPLATES:
            # Preserve only the query when the catalogue uses it to identify an account.
            candidate = base + ("?" + p.query if "?" in template else "")
            match = pattern.fullmatch(candidate)
            if not match or match["handle"].lower() in _RESERVED | _RESERVED_ROUTES.get(name, set()):
                continue
            handle = match["handle"]
            # Bluesky's catalogue adds this suffix; return the actual account handle.
            if name == "Bluesky" and ".bsky.social" in template:
                handle += ".bsky.social"
                url = "https://bsky.app/profile/" + quote(handle, safe="")
            else:
                url = template.format(username=quote(handle, safe=""))
            if validate_network:
                _refuse_internal(url)
            return {"platform": name, "handle": handle, "url": url}
    except (ValueError, BlockedRequest):
        return None
    return None


def account_key(profile):
    parsed = account_url(profile.get("url"), validate_network=False)
    return (parsed["platform"].casefold(), parsed["handle"].casefold()) if parsed else (profile.get("platform", "").casefold(), profile.get("handle", "").casefold())


def connections(result, network_checks=None):
    """No fetching of owner URLs or discovered emails, and no automatic recursion."""
    rows, seen, destinations = [], set(), set()
    trail = result.get("connection_trail", [])
    visited = {account_key(edge["source"]) for edge in trail} | {account_key(edge["destination"]) for edge in trail}
    network_checks = network_checks if network_checks is not None else {}

    def add(source, raw, kind, explanation, verification=None):
        destination = account_url(raw, validate_network=False)
        if not destination:
            return
        host = urlsplit(destination["url"]).hostname
        if host not in network_checks:
            try:
                _refuse_internal(destination["url"])
                network_checks[host] = True
            except (ValueError, BlockedRequest):
                network_checks[host] = False
        if not network_checks[host]:
            return
        src, dst = account_key(source), account_key(destination)
        key = (src, dst, kind)
        if src == dst or key in seen:
            return
        if dst not in destinations and len(destinations) >= MAX_SUGGESTIONS:
            return
        # Retain attribution for multiple sources but keep the response bounded too.
        if len(rows) >= MAX_SUGGESTIONS:
            return
        destinations.add(dst)
        seen.add(key)
        rows.append({"source": {k: source.get(k) for k in ("platform", "handle", "url", "source")},
                     "destination": destination, "evidence_type": kind, "explanation": explanation,
                     "verification": verification, "can_follow": kind != "same_username" and dst not in visited and len(trail) < MAX_FOLLOWS})

    profiles = result.get("activity", []) + result.get("accounts", [])
    same = sorted((p for p in profiles if result.get("mode") == "handle" and p.get("handle", "").casefold() == result["subject"].casefold()),
                  key=lambda p: (p.get("platform", ""), p.get("url", "")))
    # Compare actual profiles, so every connection retains a source profile URL.
    if len(same) > 1:
        for destination in same[1:]:
            add(same[0], destination.get("url"), "same_username",
                "These returned profiles share the searched handle. Shared usernames do not establish common ownership.")
    for source in profiles:
        for item in source.get("declared", [])[:100]:
            verification = item.get("verification")
            verified = bool(verification and verification.get("provider") == "Mastodon" and verification.get("verified_at"))
            add(source, item.get("url"), "platform_verified" if verified else "profile_link",
                "Mastodon reports a verified reciprocal profile-field link." if verified else "An explicit account link was published in this profile's public metadata; ownership is not independently confirmed.",
                verification if verified else None)
    identity = result.get("identity")
    if identity:
        source = {"platform": "Keybase", "handle": identity["username"], "url": identity["url"], "source": identity["source"]}
        for proof in identity.get("proofs", []):
            verification = proof.get("verification")
            verified = bool(verification and verification.get("provider") == "Keybase" and verification.get("state") == 1 and verification.get("proof_url"))
            add(source, proof.get("url"), "platform_verified" if verified else "profile_link",
                "Keybase reports an account proof with successful state; MyRecon has not revalidated its signature." if verified else "Keybase publishes this account link without successful verification evidence in this response.", verification if verified else None)
    return rows


def _signer():
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="deep-search-follow-v1")


def attach_actions(data, uid):
    data = copy.deepcopy(data)
    for row in data.get("connections", []):
        row["action"] = None
        if row["can_follow"]:
            edge = {k: row[k] for k in ("source", "destination", "evidence_type", "explanation", "verification")}
            token = _signer().dumps({"uid": uid, "trail": data.get("connection_trail", []) + [edge]})
            row["action"] = {"method": "POST", "endpoint": "/api/investigate/stream", "body": {"follow_token": token}, "requires_user_action": True}
    return data


def parse_follow(token, uid):
    if not isinstance(token, str) or len(token) > 20000:
        raise ValidationError("Invalid follow action. Run the source search again.")
    try:
        payload = _signer().loads(token, max_age=3600)
    except BadSignature:
        raise ValidationError("Follow action expired or is invalid. Run the source search again.") from None
    trail = payload.get("trail", [])
    if payload.get("uid") != uid or not 1 <= len(trail) <= MAX_FOLLOWS:
        raise ValidationError("Invalid follow action.")
    destination = trail[-1]["destination"]
    checked = account_url(destination["url"])
    if not checked or account_key(checked) != account_key(destination):
        raise ValidationError("The linked destination is unavailable or blocked.")
    previous = {account_key(edge["source"]) for edge in trail} | {account_key(edge["destination"]) for edge in trail[:-1]}
    if account_key(destination) in previous:
        raise ValidationError("This account has already been followed.")
    parsed = parse_input("@" + destination["handle"])
    return {**parsed, "connection_trail": trail}
