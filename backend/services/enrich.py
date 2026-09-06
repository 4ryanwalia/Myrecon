"""
Single-platform enrichment.

Exists because of an address-reputation problem, not a code one. The sweep runs
on-device precisely because phones get better treatment than datacentres, and
for most platforms that holds. Instagram is the exception in the other
direction: it answers a residential phone, a datacentre server, or neither,
depending on the hour and how much that address has asked lately. Measured the
same minute, the deployed backend returned a full profile for `nasa` while a
development laptop got 401 for every handle including Instagram's own.

So this endpoint lets a client that has been refused borrow an address that has
not. It is deliberately one platform and one handle — not a second sweep —
because the caller already knows what it wants and a full scan would be a
minute of work to answer a question about one avatar.
"""

from modules.enrichment import ProfileEnricher
from modules.username_checker import PLATFORMS

# Platform name -> URL template, from the same table the sweep uses, so a URL
# built here can never drift from the one that was checked.
_TEMPLATES = {name: template for name, template, _ in PLATFORMS}

# Fields worth returning. The enricher also carries raw image bytes and other
# internals that have no business crossing the wire.
_PUBLIC_FIELDS = (
    "platform", "username", "url", "display_name", "bio", "profile_pic_url",
    "followers", "following", "posts", "is_private", "is_verified", "error",
)


def enrich_profile(platform: str, username: str) -> dict:
    """
    Enrich one profile and return only the presentable fields.

    A platform with no enricher, or one that fails, comes back with whatever is
    known and no error — the caller asked for extra detail, not for existence,
    and an empty answer is a valid one.
    """
    template = _TEMPLATES.get(platform)
    if not template:
        return {
            "status": "error",
            "error": f"Unknown platform: {platform}",
        }

    result = {
        "platform": platform,
        "username": username,
        "url": template.replace("{username}", username),
        "exists": True,
    }

    try:
        ProfileEnricher(delay=0).enrich(result)
    except Exception as e:  # noqa: BLE001 - enrichment is additive, never fatal
        result["error"] = f"Enrichment failed: {type(e).__name__}"

    # Raw bytes never leave the server; the URL is what a client renders.
    result.pop("profile_pic_data", None)

    return {
        "status": "ok",
        "query": {"platform": platform, "username": username},
        "profile": {k: result[k] for k in _PUBLIC_FIELDS if k in result},
    }
