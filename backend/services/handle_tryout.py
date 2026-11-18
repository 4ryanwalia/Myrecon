"""Website creator handle comparisons, checked in bounded, independent batches."""
import re
import threading
from urllib.parse import urlsplit

import config
from core import responses
from core.netguard import safe_get
from core.validation import ValidationError
from modules.sweep import CATALOGUE, EXTRA, Sweep


# Omit duplicate account namespaces, retired sites, ID-only lookups and pages
# for packages, groups or other objects rather than a creator's public name.
_OMIT = {
    "Gist", "Hashnode Blog", "Blogspot", "Untappd Beer", "Untappd Venue",
    "Product Hunt Maker", "Steam Community Group", "Genius Artists", "Instructables Member",
    "Duelingbook Deck", "Duelingbook", "NationStates Region", "NationStates Nation",
    "Homebrew", "Telegraph", "Post.news", "Ello", "Glitch", "Caffeine", "Taringa",
    "Read.cv", "Bento", "Polywork", "Superpeer", "Publons", "AngelList", "ORCID",
    "StackOverflow", "Strava", "Komoot", "Mercari", "Care2", "Chegg", "Guilded",
    "GooglePlayStore", "2Dimensions", "RoyalCams", "1337x", "EyeEm", "Foursquare",
    "Code Snippet Wiki", "OnlyFans", "Fosstodon", "chaos.social", "mastodon.cloud",
    "mastodon.xyz", "mstdn.io", "mstdn.social", "Mamot", "Framapiaf", "social.tchncs.de",
    "GoFundMe", "Bilibili", "Nextdoor", "Nyaa.si", "Mirror.xyz", "ShitpostBot5000",
}
_EXTRA_NAMES = {
    "Figma": "Figma", "Gog": "GOG", "domestika.org": "Domestika",
    "DigitalOcean": "DigitalOcean", "flipsnack.com": "Flipsnack",
    "community.dropbox.com": "Dropbox Community", "community.openai.com": "OpenAI Developer Community",
    "community.postman.com": "Postman Community", "community.grafana.com": "Grafana Community",
    "community.jenkins.io": "Jenkins Community", "community.fastly.com": "Fastly Community",
    "community.eufy.com": "Eufy Community", "community.smartthings.com": "SmartThings Community",
    "community.frame.work": "Framework Community", "community.norton.com": "Norton Community",
    "forum.godotengine.org": "Godot Forum", "forums.sketchup.com": "SketchUp Community",
    "discuss.kde.org": "KDE Discuss", "discuss.hashicorp.com": "HashiCorp Discuss",
    "discuss.roboflow.com": "Roboflow Community", "Mapillary Forum": "Mapillary Forum",
}
_POPULAR = (
    "Instagram", "YouTube", "TikTok", "GitHub", "Reddit", "Twitter / X", "Twitch",
    "Facebook", "LinkedIn", "Pinterest", "Snapchat", "Threads", "Bluesky", "Tumblr",
    "Medium", "Substack", "Patreon", "Linktree", "Behance", "Dribbble", "Figma",
    "Spotify", "SoundCloud", "Bandcamp", "Steam", "Roblox", "Chess.com", "GitLab",
    "Dev.to", "Hacker News", "Etsy", "eBay",
)
_platforms = [p for p in CATALOGUE if p["name"] not in _OMIT]
_platforms.extend({**p, "name": _EXTRA_NAMES[p["name"]]} for p in EXTRA if p["name"] in _EXTRA_NAMES)
PLATFORMS = {p["name"]: p for p in _platforms}
BATCH_SIZE = 24
_slots = threading.BoundedSemaphore(2)


def _profile_get(url, **kwargs):
    # Restrict each request and its redirects to the platform's public host.
    host = urlsplit(url).hostname.removeprefix("www.")
    redirects = 3 if kwargs.pop("allow_redirects", True) else 0
    return safe_get(url, allowed_hosts={host, "www." + host}, redirect_limit=redirects, **kwargs)


class _TryoutSweep(Sweep):
    def __init__(self, handle):
        super().__init__(handle, deadline_seconds=24, concurrency=min(8, config.SWEEP_CONCURRENCY))
        self.session.get = _profile_get

    def _page_avatar(self, p, handle):
        # The tryout only needs the public profile verdict.
        return None


def check_batch(handle, names):
    hits, _ = _TryoutSweep(handle).run(platforms=[PLATFORMS[name] for name in names])
    rows = []
    for hit in hits:
        verdict, reason = hit["verdict"], hit["reason"]
        if hit["reason_code"] == "out_of_time":
            verdict = "unchecked"
        elif hit["reason_code"] == "differential":
            verdict, reason = "unknown", "The page differed from a missing profile, but the handle could not be confirmed."
        row = {"platform": hit["platform"], "verdict": verdict, "reason": reason}
        if verdict == "found":
            row["url"] = hit["url"]
        rows.append(row)
    return rows


def register(app, json_body):
    @app.get("/api/handle-tryout/platforms")
    def handle_tryout_platforms():
        platforms = [{"name": p["name"], "category": p["category"]} for p in PLATFORMS.values()]
        return responses.ok({"platforms": platforms, "popular": list(_POPULAR), "batchSize": BATCH_SIZE})

    @app.post("/api/handle-tryout/check")
    def handle_tryout_check():
        data = json_body()
        if not isinstance(data, dict):
            raise ValidationError("Expected a handle and platform selection.")
        handle, names = data.get("handle"), data.get("platforms")
        if not isinstance(handle, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,38}", handle):
            raise ValidationError("Enter a valid handle of up to 39 characters.")
        if (not isinstance(names, list) or not 1 <= len(names) <= BATCH_SIZE
                or any(not isinstance(n, str) or n not in PLATFORMS for n in names)
                or len(set(names)) != len(names)):
            raise ValidationError("Select distinct platforms from the handle tryout catalog.")
        if not _slots.acquire(blocking=False):
            response, status = responses.error("The platform checker is busy.", 503, "busy")
            response.headers["Retry-After"] = "5"
            return response, status
        try:
            return responses.ok({"handle": handle, "results": check_batch(handle, names)})
        finally:
            _slots.release()
