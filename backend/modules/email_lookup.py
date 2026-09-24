"""
Email intelligence — reliable sources only.

The previous version fanned out to ~50 undocumented private "email exists"
endpoints (Spotify, Adobe, Discord, banks, ...). Those break constantly and
produce false positives, so they have been removed in favour of a small set
of sources that are documented, stable, and accurate:

  • Format & provider analysis   (local, deterministic)
  • MX validation via DNS-over-HTTPS
  • Gravatar profile + avatar     (public, documented)
  • LeakCheck public breach API   (free, documented)
  • XposedOrNot breach analytics  (free, documented — per-breach detail)
  • Have I Been Pwned             (official API, when a key is configured)
  • GitHub commit-email search    (official API)
"""

import hashlib
import os
from typing import Optional

import requests

from modules.network import _doh_query

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA}


def _source_status(source: dict) -> str:
    state = source.get("status") or ("ok" if source else "unknown")
    if state not in ("skipped", "unconfigured", "rate_limited") and (source.get("error") or source.get("checked") is False):
        return "unavailable"
    return state


def _worst_status(breaches: dict, fallback: Optional[dict], darkweb: dict) -> str:
    """One word for how much the breach answer can be trusted.

    Ordered by how misleading a clean-looking result would be. If ANY source
    was rate-limited or down, the absence of findings is not evidence of
    safety, and the client is told so rather than left to infer it from an
    empty list.

    "partial" is the case worth naming: one source answered and another did
    not, so there are real findings on screen AND a gap behind them.
    """
    states = [_source_status(breaches)]
    if fallback:
        states.append(_source_status(fallback))
    if darkweb:
        states.append(_source_status(darkweb))

    answered = [x for x in states if x == "ok"]
    broken = [x for x in states if x not in ("ok", "skipped", "unconfigured")]

    if not broken and answered:
        return "ok"
    if "rate_limited" in broken:
        return "partial_rate_limited" if answered else "rate_limited"
    return "partial_unavailable" if answered else "unavailable"


def _retry_after(resp) -> Optional[int]:
    """Seconds the server asked us to wait, when it says.

    Both breach sources can answer 429, and neither documents a retry-after
    header, so this is usually None. Reading the header when it is there rather
    than guessing is the difference between telling someone "try again in 2
    seconds" and inventing a cooldown they then wait out for no reason.
    """
    raw = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
    try:
        return max(0, int(str(raw).strip()))
    except (TypeError, ValueError):
        return None
_TIMEOUT = 10
# Breach analytics returns a large document (150 KB+ for heavily exposed
# addresses), so it gets a longer budget than the other lookups.
_ANALYTICS_TIMEOUT = 20
# Per-breach records sent to the client, most records-leaked first. The full
# count is still reported; this only bounds the response payload.
_MAX_BREACH_DETAILS = 30


def _first(value):
    """XposedOrNot returns some metrics as a bare object and others wrapped in
    a single-element list, depending on the field. Normalise both to an object."""
    if isinstance(value, list):
        return value[0] if value else {}
    return value or {}


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _flatten_categories(tree: dict) -> list:
    """
    Flatten XposedOrNot's nested xposed_data tree into a ranked list of the
    data types that actually leaked:

        {"children": [{"name": "🔒 Security Practices",
                       "children": [{"name": "data_Passwords", "value": 142}]}]}
        → [{"name": "Passwords", "category": "Security Practices", "count": 142}]
    """
    out = []
    for group in (tree or {}).get("children") or []:
        # Category labels ship with a leading emoji; keep the words only.
        raw = str(group.get("name", ""))
        category = "".join(c for c in raw if c.isalnum() or c in " &-/").strip()
        for leaf in group.get("children") or []:
            name = str(leaf.get("name", ""))
            out.append({
                "name": name[5:] if name.startswith("data_") else name,
                "category": category,
                "count": _int(leaf.get("value")),
            })
    return sorted(out, key=lambda x: x["count"], reverse=True)


class EmailLookup:
    DISPOSABLE_DOMAINS = {
        "tempmail.com", "guerrillamail.com", "throwaway.email", "yopmail.com",
        "mailinator.com", "10minutemail.com", "trashmail.com", "sharklasers.com",
        "guerrillamailblock.com", "grr.la", "dispostable.com", "fakeinbox.com",
        "temp-mail.org", "emailondeck.com", "getnada.com", "mohmal.com",
        "maildrop.cc", "mintemail.com", "tempinbox.com", "burnermail.io",
    }

    PROVIDER_INFO = {
        "gmail.com": ("Google Gmail", "personal"),
        "googlemail.com": ("Google Gmail", "personal"),
        "yahoo.com": ("Yahoo Mail", "personal"),
        "outlook.com": ("Microsoft Outlook", "personal"),
        "hotmail.com": ("Microsoft Hotmail", "personal"),
        "live.com": ("Microsoft Live", "personal"),
        "icloud.com": ("Apple iCloud", "personal"),
        "me.com": ("Apple iCloud", "personal"),
        "protonmail.com": ("Proton Mail", "privacy"),
        "proton.me": ("Proton Mail", "privacy"),
        "tutanota.com": ("Tutanota", "privacy"),
        "aol.com": ("AOL Mail", "personal"),
        "zoho.com": ("Zoho Mail", "business"),
        "mail.ru": ("Mail.ru", "personal"),
        "yandex.com": ("Yandex Mail", "personal"),
        "gmx.com": ("GMX Mail", "personal"),
        "fastmail.com": ("Fastmail", "privacy"),
    }

    def __init__(self, hibp_api_key: Optional[str] = None):
        # Parameter kept so existing callers still construct; it is ignored.
        # Have I Been Pwned was removed because it is the only source here that
        # needs a paid subscription. XposedOrNot's check-email endpoint covers
        # the same job — "is this address in anything" — without a key.
        del hibp_api_key

    # ── Format & provider analysis ───────────────────────────────
    def analyze(self, email: str) -> dict:
        local, _, domain = email.partition("@")
        provider_name, provider_type = self.PROVIDER_INFO.get(
            domain, ("Custom / corporate domain", "custom")
        )

        mx = _doh_query(domain, "MX")
        return {
            "email": email,
            "local_part": local,
            "domain": domain,
            "provider": provider_name,
            "provider_type": provider_type,
            "disposable": domain in self.DISPOSABLE_DOMAINS,
            "has_mx": bool(mx),
            "mx_hosts": [r["value"] for r in mx][:5],
            "deliverable": bool(mx),
            "plus_addressing": "+" in local,
            "format": self._format_hint(local),
        }

    @staticmethod
    def _format_hint(local: str) -> str:
        has_dot = "." in local
        has_num = any(c.isdigit() for c in local)
        if has_dot and not has_num:
            return "name-based"
        if has_num and len(local) <= 6:
            return "short-handle"
        return "generic"

    # ── Gravatar ─────────────────────────────────────────────────
    def gravatar(self, email: str) -> dict:
        digest = hashlib.md5(email.strip().lower().encode()).hexdigest()
        profile_url = f"https://en.gravatar.com/{digest}.json"
        avatar_url = f"https://www.gravatar.com/avatar/{digest}?s=400&d=404"
        result = {"exists": False, "profile_url": "", "avatar_url": "",
                  "display_name": "", "bio": "", "accounts": []}
        try:
            resp = requests.get(profile_url, headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code == 200:
                entry = (resp.json().get("entry") or [{}])[0]
                result["exists"] = True
                result["display_name"] = entry.get("displayName", "")
                result["bio"] = (entry.get("aboutMe") or "")[:280]
                result["profile_url"] = entry.get("profileUrl", profile_url)
                thumb = entry.get("thumbnailUrl") or avatar_url
                result["avatar_url"] = thumb.split("?")[0] + "?s=400"
                for acc in entry.get("accounts", [])[:12]:
                    result["accounts"].append({
                        "name": acc.get("name", acc.get("shortname", "")),
                        "url": acc.get("url", ""),
                    })
            else:
                av = requests.get(avatar_url, headers=_HEADERS, timeout=6)
                if av.status_code == 200:
                    result["exists"] = True
                    result["avatar_url"] = avatar_url
        except requests.RequestException:
            pass
        return result

    # ── LeakCheck (free public breach API) ───────────────────────
    #
    # Rate limit, from LeakCheck's own docs: the Public API is allowed 1 request
    # per second. That is the only published figure — there is no documented
    # daily quota, and the body returned on a 429 is not documented either. So
    # a limit here clears in about a second, and any copy telling the user to
    # "come back tomorrow" would be inventing a cooldown that does not exist.
    # `retry_after` carries the server's own number when it sends one.
    def breaches(self, email: str) -> dict:
        result = {"checked": True, "breached": False, "count": 0,
                  "fields": [], "sources": [], "source_api": "LeakCheck",
                  "status": "ok"}
        try:
            resp = requests.get(
                "https://leakcheck.io/api/public",
                params={"check": email},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                if not isinstance(data, dict) or not isinstance(data.get("success"), bool) or data.get("error"):
                    raise ValueError("Unrecognized breach response")
                if data.get("success") and (not isinstance(data.get("found"), int) or data["found"] < 0):
                    raise ValueError("Unreadable breach count")
                if not isinstance(data.get("sources", []), list) or any(not isinstance(s, dict) for s in data.get("sources", [])):
                    raise ValueError("Unreadable breach sources")
                if data.get("success") and data.get("found", 0) > 0:
                    result["breached"] = True
                    result["count"] = data["found"]
                    result["fields"] = data.get("fields", [])
                    result["sources"] = [
                        {"name": s.get("name", "Unknown"), "date": s.get("date", "")}
                        for s in data.get("sources", [])
                    ]
            elif resp.status_code == 429:
                result["status"] = "rate_limited"
                result["retry_after"] = _retry_after(resp)
                result["error"] = "Breach service is rate-limited."
            elif resp.status_code >= 500:
                result["status"] = "unavailable"
                result["error"] = "Breach service is having problems."
            else:
                result["status"] = "unavailable"
                result["error"] = f"Breach service answered {resp.status_code}."
        except (requests.RequestException, ValueError):
            result["status"] = "unavailable"
            result["error"] = "Breach service was unreachable or returned an unreadable reply."
        # "We could not ask" must never render as "you are clean".
        if result["status"] != "ok":
            result["checked"] = False
        return result

    # ── XposedOrNot check-email (free, no key) ───────────────────
    #
    # The fallback for when LeakCheck will not answer. Keyless, which is the
    # whole point: it replaced Have I Been Pwned here because HIBP needs a paid
    # subscription, and every other source in this app is free to call.
    #
    # Its contract, read off the live endpoint rather than assumed:
    #
    #   found   200 {"breaches": [["Adobe", "Dropbox", ...]], "email": "...",
    #                "status": "success"}
    #   clean   200 {"Error": "Not found", "email": null}
    #   blocked 200 text/html — a Cloudflare interstitial
    #
    # Two traps in that. `breaches` is a list CONTAINING one list, not a list of
    # names, so it needs flattening. And "Not found" arrives with HTTP 200 and
    # the word Error in it while actually being a clean result — reading it as
    # a failure would turn every unbreached address into "we could not check",
    # which is the same lie as the reverse, just in the other direction.
    #
    # It returns names only: no dates, no field classes. That is thinner than
    # breach-analytics, which runs separately in darkweb() and carries the
    # detail. This one exists to answer "is this address in anything" when the
    # primary source is throttled.
    def xposed_check_email(self, email: str) -> dict:
        out = {"source": "XposedOrNot", "status": "ok", "breached": False,
               "count": 0, "sources": []}
        try:
            resp = requests.get(
                f"https://api.xposedornot.com/v1/check-email/{email}",
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            if resp.status_code == 429:
                out.update(status="rate_limited", retry_after=_retry_after(resp),
                           error="XposedOrNot is rate-limiting us.")
                return out
            if resp.status_code >= 500:
                out.update(status="unavailable", error="XposedOrNot is having problems.")
                return out
            if resp.status_code != 200:
                out.update(status="unavailable",
                           error=f"XposedOrNot answered {resp.status_code}.")
                return out

            # A bot check is served as HTML with a 200. Not an answer.
            if "json" not in resp.headers.get("Content-Type", "").lower():
                out.update(status="unavailable", error="XposedOrNot served a challenge page.")
                return out

            data = resp.json()
            if not isinstance(data, dict):
                out.update(status="unavailable", error="XposedOrNot sent an unreadable reply.")
                return out

            # The documented clean answer. Note it is keyed "Error".
            if data.get("Error"):
                if str(data["Error"]).strip().lower() != "not found":
                    out.update(status="unavailable", error="XposedOrNot could not complete the lookup.")
                return out
            if not isinstance(data.get("breaches"), list):
                out.update(status="unavailable", error="XposedOrNot sent an unrecognized reply.")
                return out
            if any(not isinstance(group, (str, list)) or
                   (isinstance(group, list) and any(not isinstance(n, str) for n in group))
                   for group in data["breaches"]):
                out.update(status="unavailable", error="XposedOrNot sent unreadable breach names.")
                return out

            names = []
            for group in data.get("breaches") or []:
                if isinstance(group, list):
                    names.extend(n for n in group if isinstance(n, str) and n.strip())
                elif isinstance(group, str) and group.strip():
                    names.append(group)

            seen, unique = set(), []
            for n in names:
                key = n.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(n.strip())

            if unique:
                out.update(breached=True, count=len(unique),
                           sources=[{"name": n, "date": ""} for n in unique[:50]])
            return out
        except ValueError:
            out.update(status="unavailable", error="XposedOrNot sent malformed JSON.")
            return out
        except requests.RequestException:
            out.update(status="unavailable", error="XposedOrNot was unreachable.")
            return out

    # ── XposedOrNot breach analytics (free, no key) ──────────────
    def darkweb(self, email: str) -> dict:
        """
        Per-breach exposure detail from published breach corpora.

        This is the same class of data commercial "dark web monitoring"
        products resell: credentials recovered from dumps that were traded on
        criminal forums and later published. It is *not* a live crawl of onion
        services — no free source offers that, and the UI says so plainly.
        """
        result = {
            "checked": False, "status": "unavailable", "breached": False, "count": 0,
            "risk_label": "", "risk_score": 0, "records_exposed": 0,
            "breaches": [], "timeline": [], "exposed_data": [],
            "password_strength": {}, "pastes": 0, "source_api": "XposedOrNot",
        }
        try:
            resp = requests.get(
                "https://api.xposedornot.com/v1/breach-analytics",
                params={"email": email},
                headers=_HEADERS,
                timeout=_ANALYTICS_TIMEOUT,
            )
            if resp.status_code == 429:
                result.update(status="rate_limited", retry_after=_retry_after(resp),
                              error="Breach analytics rate-limited — try again shortly.")
                return result
            if resp.status_code != 200:
                result["error"] = f"Breach analytics answered {resp.status_code}."
                return result
            data = resp.json()
            if not isinstance(data, dict) or "ExposedBreaches" not in data:
                result["error"] = "Breach analytics returned an unrecognized reply."
                return result
            exposed = data.get("ExposedBreaches")
            if exposed is not None and not isinstance(exposed, dict):
                result["error"] = "Breach analytics returned an unreadable reply."
                return result
            if exposed is not None and "breaches_details" not in exposed:
                result["error"] = "Breach analytics returned incomplete breach details."
                return result
            details = (exposed or {}).get("breaches_details") or []
            if not isinstance(details, list) or any(not isinstance(b, dict) for b in details):
                result["error"] = "Breach analytics returned unreadable breach details."
                return result
            result.update(checked=True, status="ok")
        except (requests.RequestException, ValueError):
            result["error"] = "Breach analytics service was unreachable."
            return result

        # A clean address answers 200 with every member null, not 404.
        if not details:
            return result

        result["breached"] = True
        result["count"] = len(details)

        ranked = sorted(details, key=lambda b: _int(b.get("xposed_records")), reverse=True)
        result["records_exposed"] = sum(_int(b.get("xposed_records")) for b in details)
        result["breaches"] = [{
            "name": b.get("breach", ""),
            "domain": b.get("domain", ""),
            "date": str(b.get("xposed_date", "")),
            "records": _int(b.get("xposed_records")),
            "industry": b.get("industry", ""),
            "verified": str(b.get("verified", "")).lower() == "yes",
            "password_risk": b.get("password_risk", ""),
            "logo": b.get("logo", ""),
            "exposed": [p.strip() for p in str(b.get("xposed_data", "")).split(";") if p.strip()],
            "details": _clip(b.get("details", ""), 260),
        } for b in ranked[:_MAX_BREACH_DETAILS]]

        metrics = data.get("BreachMetrics") or {}
        risk = _first(metrics.get("risk"))
        result["risk_label"] = risk.get("risk_label", "")
        result["risk_score"] = _int(risk.get("risk_score"))
        result["password_strength"] = _first(metrics.get("passwords_strength"))

        # yearwise_details is {"y2007": 0, "y2008": 3, ...} — keep the years
        # that actually saw a breach so the client can chart them directly.
        years = _first(metrics.get("yearwise_details"))
        result["timeline"] = [
            {"year": int(k[1:]), "count": _int(v)}
            for k, v in sorted(years.items())
            if k.startswith("y") and k[1:].isdigit() and _int(v) > 0
        ]

        result["exposed_data"] = _flatten_categories(_first(metrics.get("xposed_data")))
        result["pastes"] = _int((data.get("PastesSummary") or {}).get("cnt"))
        return result

    # ── GitHub commit-email search (official API) ────────────────
    def github(self, email: str) -> Optional[dict]:
        try:
            headers = {**_HEADERS, "Accept": "application/vnd.github+json"}
            token = os.environ.get("GITHUB_TOKEN", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            resp = requests.get(
                "https://api.github.com/search/users",
                params={"q": f"{email} in:email"},
                headers=headers,
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    u = items[0]
                    return {
                        "username": u.get("login", ""),
                        "url": u.get("html_url", ""),
                        "avatar_url": u.get("avatar_url", ""),
                    }
        except requests.RequestException:
            pass
        return None

    # ── Orchestration ────────────────────────────────────────────
    def scan(self, email: str) -> dict:
        analysis = self.analyze(email)
        gravatar = self.gravatar(email)
        breaches = self.breaches(email)
        darkweb = self.darkweb(email)
        # The fallback, not a parallel call. It runs when LeakCheck could not
        # answer — rate-limited, unreachable, or erroring — which is exactly
        # when a second opinion is worth having. When LeakCheck answered there
        # is nothing to cover for, and the request is skipped.
        fallback = (self.xposed_check_email(email)
                    if breaches.get("status") != "ok"
                    else {"source": "XposedOrNot", "status": "skipped",
                          "breached": False, "count": 0, "sources": []})
        github = self.github(email)

        linked = []
        if gravatar["exists"]:
            linked.append("Gravatar")
        if github:
            linked.append("GitHub")
        for acc in gravatar.get("accounts", []):
            if acc.get("name"):
                linked.append(acc["name"])

        # Breach count = distinct named breaches across every source, not the
        # record tally. LeakCheck's "found" counts leaked *rows* (often
        # thousands for one address), so using it as a breach count both
        # overstated exposure and pinned the client's score to maximum.
        names = {s.get("name", "").strip().lower()
                 for s in breaches.get("sources") or [] if s.get("name")}
        names |= {b["name"].strip().lower() for b in darkweb["breaches"] if b.get("name")}
        if fallback and fallback.get("status") == "ok":
            names |= {s.get("name", "").strip().lower()
                      for s in fallback.get("sources") or [] if s.get("name")}
        # darkweb["count"] covers every breach found, including any trimmed
        # from the detail list by _MAX_BREACH_DETAILS.
        breach_count = max(len(names), darkweb["count"])
        coverage = []
        for name, source in (("LeakCheck", breaches), ("XposedOrNot analytics", darkweb),
                             ("XposedOrNot fallback", fallback)):
            state = _source_status(source)
            coverage.append({"name": name, "status": state,
                             "checked": state == "ok" and source.get("checked", True),
                             "error": source.get("error"), "retry_after": source.get("retry_after")})
        completed = sum(c["checked"] for c in coverage)
        attempted = sum(c["status"] not in ("skipped", "unconfigured") for c in coverage)
        breached = bool(breaches.get("breached") or darkweb["breached"] or fallback.get("breached"))
        outcome = ("found" if breached else "unavailable" if not completed
                   else "incomplete" if completed < attempted else "no_match")

        return {
            "query": {"email": email},
            "analysis": analysis,
            "gravatar": gravatar,
            "github": github,
            "breaches": breaches,
            "darkweb": darkweb,
            "fallback": fallback,
            "summary": {
                "linked_accounts": sorted(set(linked)),
                "breached": breached,
                "breach_outcome": outcome,
                "breach_coverage": {"completed": completed, "attempted": attempted, "sources": coverage},
                # What the client needs to tell the user why a result is thin.
                # Without it, "no breaches found" and "nobody would answer us"
                # arrive on the screen looking identical.
                "breach_status": _worst_status(breaches, fallback, darkweb),
                "retry_after": max((c["retry_after"] or 0 for c in coverage), default=0) or None,
                "breach_count": breach_count,
                "records_found": breaches.get("count", 0),
                "records_exposed": darkweb["records_exposed"],
                "risk_label": darkweb["risk_label"],
                "risk_score": darkweb["risk_score"],
                "deliverable": analysis["deliverable"],
                "disposable": analysis["disposable"],
            },
        }
