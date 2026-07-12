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

        breach_count = breaches.get("count", 0)
        if hibp and hibp.get("count"):
            breach_count = max(breach_count, hibp["count"])

        return {
            "query": {"email": email},
            "analysis": analysis,
            "gravatar": gravatar,
            "github": github,
            "breaches": breaches,
            "hibp": hibp,
            "summary": {
                "linked_accounts": sorted(set(linked)),
                "breached": bool(breaches.get("breached") or (hibp and hibp.get("breached"))),
                "breach_count": breach_count,
                "deliverable": analysis["deliverable"],
                "disposable": analysis["disposable"],
            },
        }
