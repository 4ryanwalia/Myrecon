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
        self.hibp_api_key = hibp_api_key or os.environ.get("HIBP_API_KEY", "")

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
    def breaches(self, email: str) -> dict:
        result = {"checked": True, "breached": False, "count": 0,
                  "fields": [], "sources": [], "source_api": "LeakCheck"}
        try:
            resp = requests.get(
                "https://leakcheck.io/api/public",
                params={"check": email},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("found", 0) > 0:
                    result["breached"] = True
                    result["count"] = data["found"]
                    result["fields"] = data.get("fields", [])
                    result["sources"] = [
                        {"name": s.get("name", "Unknown"), "date": s.get("date", "")}
                        for s in data.get("sources", [])
                    ]
            elif resp.status_code == 429:
                result["error"] = "Breach service rate-limited — try again shortly."
        except requests.RequestException:
            result["error"] = "Breach service was unreachable."
        return result

    # ── Have I Been Pwned (official API, needs a key) ────────────
    def hibp(self, email: str) -> Optional[dict]:
        if not self.hibp_api_key:
            return None
        try:
            resp = requests.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                headers={**_HEADERS, "hibp-api-key": self.hibp_api_key},
                params={"truncateResponse": "false"},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                items = resp.json()
                return {
                    "breached": True,
                    "count": len(items),
                    "sources": [
                        {"name": b.get("Name", ""), "date": b.get("BreachDate", "")}
                        for b in items[:25]
                    ],
                }
            if resp.status_code == 404:
                return {"breached": False, "count": 0, "sources": []}
        except requests.RequestException:
            pass
        return None

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
            "checked": True, "breached": False, "count": 0,
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
                result["error"] = "Breach analytics rate-limited — try again shortly."
                return result
            if resp.status_code != 200:
                return result
            data = resp.json() or {}
        except (requests.RequestException, ValueError):
            result["error"] = "Breach analytics service was unreachable."
            return result

        # A clean address answers 200 with every member null, not 404.
        details = (data.get("ExposedBreaches") or {}).get("breaches_details") or []
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
        hibp = self.hibp(email)
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
        if hibp:
            names |= {s.get("name", "").strip().lower()
                      for s in hibp.get("sources") or [] if s.get("name")}
        # darkweb["count"] covers every breach found, including any trimmed
        # from the detail list by _MAX_BREACH_DETAILS.
        breach_count = max(len(names), darkweb["count"])

        return {
            "query": {"email": email},
            "analysis": analysis,
            "gravatar": gravatar,
            "github": github,
            "breaches": breaches,
            "darkweb": darkweb,
            "hibp": hibp,
            "summary": {
                "linked_accounts": sorted(set(linked)),
                "breached": bool(breaches.get("breached")
                                 or darkweb["breached"]
                                 or (hibp and hibp.get("breached"))),
                "breach_count": breach_count,
                "records_found": breaches.get("count", 0),
                "records_exposed": darkweb["records_exposed"],
                "risk_label": darkweb["risk_label"],
                "risk_score": darkweb["risk_score"],
                "deliverable": analysis["deliverable"],
                "disposable": analysis["disposable"],
            },
        }
