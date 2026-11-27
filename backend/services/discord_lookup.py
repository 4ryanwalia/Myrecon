"""
Discord user profile lookup for /discord-id-lookup.html.

Calls Discord's documented `GET /users/{user.id}` with a bot token
(docs.discord.com/developers/resources/user, read 28 Nov 2026) and returns
only what Discord's public profile shows anyway: username, display name,
avatar, banner, accent colour and public badges. A bot token cannot read a
user's email or phone, and nothing else is requested.

Without DISCORD_BOT_TOKEN the lookup reports "not_configured" and the page
keeps working as a pure in-browser ID decoder.
"""

from __future__ import annotations

import os
import re

import requests

from core.ratelimit import RateLimiter

API = "https://discord.com/api/v10"
CDN = "https://cdn.discordapp.com"
USER_AGENT = "DiscordBot (https://www.myrecon.xyz, 1.0)"
_ID = re.compile(r"^\d{15,20}$")

# Discord allows a bot 50 requests a second globally; stay well under it so a
# burst of page visitors can never earn the bot a Cloudflare ban.
_global = RateLimiter(20, 1)

# User flags as documented in the "User Flags" table, read 28 Nov 2026.
BADGES = (
    (1 << 0, "Discord Employee"),
    (1 << 1, "Partnered Server Owner"),
    (1 << 2, "HypeSquad Events Member"),
    (1 << 3, "Bug Hunter Level 1"),
    (1 << 6, "House Bravery Member"),
    (1 << 7, "House Brilliance Member"),
    (1 << 8, "House Balance Member"),
    (1 << 9, "Early Nitro Supporter"),
    (1 << 14, "Bug Hunter Level 2"),
    (1 << 16, "Verified Bot"),
    (1 << 17, "Early Verified Bot Developer"),
    (1 << 18, "Moderator Programs Alumni"),
)


def _token() -> str:
    return os.environ.get("DISCORD_BOT_TOKEN", "").strip()


def valid_id(raw: str) -> bool:
    return bool(_ID.match(raw or "")) and int(raw) < (1 << 64)


def _image(kind: str, user_id: str, image_hash: str | None) -> str | None:
    if not image_hash:
        return None
    ext = "gif" if image_hash.startswith("a_") else "png"
    return f"{CDN}/{kind}/{user_id}/{image_hash}.{ext}?size=256"


def _project(data: dict) -> dict:
    user_id = str(data.get("id", ""))
    flags = data.get("public_flags") or 0
    accent = data.get("accent_color")
    return {
        "state": "found",
        "id": user_id,
        "username": data.get("username"),
        "global_name": data.get("global_name"),
        "bot": bool(data.get("bot")),
        "avatar_url": _image("avatars", user_id, data.get("avatar")),
        "banner_url": _image("banners", user_id, data.get("banner")),
        "accent_color": f"#{accent:06x}" if isinstance(accent, int) else None,
        "badges": [name for bit, name in BADGES if flags & bit],
    }


def lookup_user(user_id: str) -> dict:
    """
    Results carrying "status": "error" are never cached by app.cached(), so a
    throttle or an outage is not pinned as an answer.
    """
    token = _token()
    if not token:
        return {"state": "not_configured"}
    allowed, retry_after = _global.check("discord")
    if not allowed:
        return {"status": "error", "state": "rate_limited", "retry_after": retry_after}
    try:
        resp = requests.get(
            f"{API}/users/{user_id}",
            headers={"Authorization": f"Bot {token}", "User-Agent": USER_AGENT},
            timeout=8,
        )
    except requests.RequestException:
        return {"status": "error", "state": "unavailable"}
    if resp.status_code == 200:
        try:
            return _project(resp.json())
        except ValueError:
            return {"status": "error", "state": "unavailable"}
    if resp.status_code == 404:
        # Unknown User: a deleted account, or the ID belongs to a server,
        # channel or message rather than a user.
        return {"state": "not_found"}
    if resp.status_code == 429:
        try:
            retry = float(resp.json().get("retry_after", 1))
        except (ValueError, AttributeError):
            retry = 1.0
        return {"status": "error", "state": "rate_limited", "retry_after": max(1, int(retry + 0.999))}
    return {"status": "error", "state": "unavailable"}
