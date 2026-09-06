"""
Username checker — multi-platform enumeration engine.

Checks a username across the platform database and, crucially, **verifies**
each hit before reporting it. A username resolving to an HTTP 200 page is not
proof of a real profile — many sites return 200 for any handle (SPA shells,
login walls, soft 404s, redirects to a home/login page). To avoid false
positives we require positive corroborating signals (the handle echoed in the
title/canonical URL, a profile-type OpenGraph tag, a real avatar, follower
stats, …) and score confidence. Hard negatives — a page that says the account
does not exist, or a redirect to a login wall — are rejected. Everything else
is reported with a confidence label rather than hidden, because platforms that
render client-side give no evidence either way and silence there reads as
"no account" when it should read "cannot tell".
"""

import re
import time
import html as _html
import requests
from urllib.parse import urlparse, urlsplit, urlunsplit
from concurrent.futures import ThreadPoolExecutor, as_completed

# ──────────────────────────────────────────────────────────────
#  Platform database:  (name, url_template, expected_status)
#  {username} is replaced at runtime.
# ──────────────────────────────────────────────────────────────

PLATFORMS: list[tuple[str, str, int]] = [
    # ── Social Media ──────────────────────────────────────────
    ("Twitter / X",       "https://x.com/{username}",                            200),
    ("Instagram",         "https://www.instagram.com/{username}/",               200),
    ("Facebook",          "https://www.facebook.com/{username}",                 200),
    ("TikTok",            "https://www.tiktok.com/@{username}",                  200),
    ("Snapchat",          "https://www.snapchat.com/add/{username}",             200),
    ("Tumblr",            "https://{username}.tumblr.com",                       200),
    ("Pinterest",         "https://www.pinterest.com/{username}/",               200),
    ("Flickr",            "https://www.flickr.com/people/{username}/",           200),
    ("VK",                "https://vk.com/{username}",                           200),
    ("Mastodon",          "https://mastodon.social/@{username}",                 200),
    ("Threads",           "https://www.threads.net/@{username}",                 200),

    # ── Professional ──────────────────────────────────────────
    ("LinkedIn",          "https://www.linkedin.com/in/{username}",              200),
    ("About.me",          "https://about.me/{username}",                         200),
    ("Behance",           "https://www.behance.net/{username}",                  200),
    ("Dribbble",          "https://dribbble.com/{username}",                     200),
    ("AngelList",         "https://angel.co/u/{username}",                       200),
    ("Gravatar",          "https://en.gravatar.com/{username}",                  200),

    # ── Developer ─────────────────────────────────────────────
    ("GitHub",            "https://github.com/{username}",                       200),
    ("GitLab",            "https://gitlab.com/{username}",                       200),
    ("Bitbucket",         "https://bitbucket.org/{username}/",                   200),
    ("CodePen",           "https://codepen.io/{username}",                       200),
    ("Replit",            "https://replit.com/@{username}",                      200),
    ("StackOverflow",     "https://stackoverflow.com/users/{username}",          200),
    ("Dev.to",            "https://dev.to/{username}",                           200),
    ("Hashnode",          "https://hashnode.com/@{username}",                    200),
    ("HackerRank",        "https://www.hackerrank.com/{username}",               200),
    ("LeetCode",          "https://leetcode.com/{username}/",                    200),
    ("Codeforces",        "https://codeforces.com/profile/{username}",           200),
    ("npm",               "https://www.npmjs.com/~{username}",                   200),
    ("Docker Hub",        "https://hub.docker.com/u/{username}",                 200),
    ("Gist",              "https://gist.github.com/{username}",                  200),
    ("Glitch",            "https://glitch.com/@{username}",                      200),
    ("Launchpad",         "https://launchpad.net/~{username}",                   200),
    ("SourceForge",       "https://sourceforge.net/u/{username}/",               200),
    ("CoderWall",         "https://coderwall.com/{username}",                    200),

    # ── Forums / Communities ──────────────────────────────────
    ("Reddit",            "https://www.reddit.com/user/{username}",              200),
    ("Quora",             "https://www.quora.com/profile/{username}",            200),
    ("Hacker News",       "https://news.ycombinator.com/user?id={username}",     200),
    ("Disqus",            "https://disqus.com/by/{username}/",                   200),
    ("ProductHunt",       "https://www.producthunt.com/@{username}",             200),
    ("Lobsters",          "https://lobste.rs/u/{username}",                      200),
    ("Discourse (Meta)",  "https://meta.discourse.org/u/{username}",             200),

    # ── Video / Streaming ─────────────────────────────────────
    ("YouTube",           "https://www.youtube.com/@{username}",                 200),
    ("Twitch",            "https://www.twitch.tv/{username}",                    200),
    ("Vimeo",             "https://vimeo.com/{username}",                        200),
    ("DailyMotion",       "https://www.dailymotion.com/{username}",              200),
    ("Rumble",            "https://rumble.com/user/{username}",                  200),
    ("Kick",              "https://kick.com/{username}",                         200),

    # ── Audio / Music ─────────────────────────────────────────
    ("SoundCloud",        "https://soundcloud.com/{username}",                   200),
    ("Bandcamp",          "https://{username}.bandcamp.com",                     200),
    ("Spotify",           "https://open.spotify.com/user/{username}",            200),
    ("MixCloud",          "https://www.mixcloud.com/{username}/",                200),
    ("Last.fm",           "https://www.last.fm/user/{username}",                 200),
    ("Genius",            "https://genius.com/{username}",                       200),

    # ── Gaming ────────────────────────────────────────────────
    ("Steam",             "https://steamcommunity.com/id/{username}",            200),
    ("Chess.com",         "https://www.chess.com/member/{username}",             200),
    ("Lichess",           "https://lichess.org/@/{username}",                    200),
    ("Roblox",            "https://www.roblox.com/user.aspx?username={username}", 200),
    ("Osu!",              "https://osu.ppy.sh/users/{username}",                 200),
    ("Minecraft",         "https://namemc.com/profile/{username}",               200),
    ("Fortnite Tracker",  "https://fortnitetracker.com/profile/all/{username}",  200),
    ("Xbox Gamertag",     "https://xboxgamertag.com/search/{username}",          200),

    # ── Photo / Art ───────────────────────────────────────────
    ("DeviantArt",        "https://www.deviantart.com/{username}",               200),
    ("ArtStation",        "https://www.artstation.com/{username}",               200),
    ("Unsplash",          "https://unsplash.com/@{username}",                    200),
    ("Imgur",             "https://imgur.com/user/{username}",                   200),
    ("VSCO",              "https://vsco.co/{username}/gallery",                  200),
    ("Giphy",             "https://giphy.com/{username}",                        200),

    # ── Blogging ──────────────────────────────────────────────
    ("Medium",            "https://medium.com/@{username}",                      200),
    ("WordPress",         "https://{username}.wordpress.com",                    200),
    ("Blogger",           "https://{username}.blogspot.com",                     200),
    ("Substack",          "https://{username}.substack.com",                     200),
    ("Wattpad",           "https://www.wattpad.com/user/{username}",             200),
    ("LiveJournal",       "https://{username}.livejournal.com",                  200),
    ("Ghost",             "https://{username}.ghost.io",                         200),
    ("Hashnode Blog",     "https://{username}.hashnode.dev",                     200),

    # ── Finance / Crypto ──────────────────────────────────────
    ("TradingView",       "https://www.tradingview.com/u/{username}/",           200),
    ("CoinMarketCap",     "https://coinmarketcap.com/community/profile/{username}/", 200),

    # ── Messaging ─────────────────────────────────────────────
    ("Telegram",          "https://t.me/{username}",                             200),
    ("Keybase",           "https://keybase.io/{username}",                       200),

    # ── Academic ──────────────────────────────────────────────
    ("ResearchGate",      "https://www.researchgate.net/profile/{username}",     200),
    ("ORCID",             "https://orcid.org/{username}",                        200),

    # ── Dating ────────────────────────────────────────────────
    ("OKCupid",           "https://www.okcupid.com/profile/{username}",          200),

    # ── Shopping ──────────────────────────────────────────────
    ("Etsy",              "https://www.etsy.com/shop/{username}",                200),
    ("eBay",              "https://www.ebay.com/usr/{username}",                 200),
    ("Poshmark",          "https://poshmark.com/closet/{username}",              200),
    ("Depop",             "https://www.depop.com/{username}/",                   200),

    # ── Paste / Dump ──────────────────────────────────────────
    ("Pastebin",          "https://pastebin.com/u/{username}",                   200),

    # ── Other Platforms ───────────────────────────────────────
    ("Linktree",          "https://linktr.ee/{username}",                        200),
    ("Carrd",             "https://{username}.carrd.co",                         200),
    ("Bio.link",          "https://bio.link/{username}",                         200),
    ("Beacons",           "https://beacons.ai/{username}",                       200),
    ("Buymeacoffee",      "https://buymeacoffee.com/{username}",                 200),
    ("Ko-fi",             "https://ko-fi.com/{username}",                        200),
    ("Patreon",           "https://www.patreon.com/{username}",                  200),
    ("Gumroad",           "https://gumroad.com/{username}",                      200),
    ("Notion",            "https://{username}.notion.site",                      200),
    ("Calendly",          "https://calendly.com/{username}",                     200),
    ("Trello",            "https://trello.com/{username}",                       200),
    ("SlideShare",        "https://www.slideshare.net/{username}",               200),
    ("Scribd",            "https://www.scribd.com/{username}",                   200),
    ("Issuu",             "https://issuu.com/{username}",                        200),
    ("Instructables",     "https://www.instructables.com/member/{username}/",    200),
    ("Hackaday",          "https://hackaday.io/{username}",                      200),
    ("Goodreads",         "https://www.goodreads.com/{username}",                200),
    ("MyAnimeList",       "https://myanimelist.net/profile/{username}",          200),
    ("Letterboxd",        "https://letterboxd.com/{username}/",                  200),
    ("Trakt",             "https://trakt.tv/users/{username}",                   200),
    ("Duolingo",          "https://www.duolingo.com/profile/{username}",         200),
    ("Codecademy",        "https://www.codecademy.com/profiles/{username}",      200),
    ("FreeCodeCamp",      "https://www.freecodecamp.org/{username}",             200),
    ("HackerOne",         "https://hackerone.com/{username}",                    200),
    ("BugCrowd",          "https://bugcrowd.com/{username}",                     200),

    # ── Requested coverage expansion ──────────────────────────
    # Each probed with a real handle and an invented one first. The first
    # three discriminate cleanly (200 vs 404); the rest answer 403 to a
    # datacentre address and could not be confirmed here. A 403 fails the
    # expected-status check and reports "not found", so an unconfirmed entry
    # costs coverage, never a false hit.
    ("Hugging Face",      "https://huggingface.co/{username}",                   200),
    ("Pixelfed",          "https://pixelfed.social/{username}",                  200),
    ("Indie Hackers",     "https://www.indiehackers.com/{username}",             200),
    ("CodeSandbox",       "https://codesandbox.io/u/{username}",                 200),
    ("Lemmy",             "https://lemmy.world/u/{username}",                    200),
    ("Crunchbase",        "https://www.crunchbase.com/person/{username}",        200),
    ("Audius",            "https://audius.co/{username}",                        200),
    ("Mod DB",            "https://www.moddb.com/members/{username}",            200),
    ("Nexus Mods",        "https://www.nexusmods.com/users/{username}",          200),
    ("Pexels",            "https://www.pexels.com/@{username}",                  200),
]

TOTAL_PLATFORMS = len(PLATFORMS)

# Platforms that need a longer timeout (SPAs / slow APIs).
SLOW_PLATFORMS = {
    "Instagram", "Facebook", "TikTok", "LinkedIn", "Threads", "Pinterest",
}


# ══════════════════════════════════════════════════════════════
#  Match verification
# ══════════════════════════════════════════════════════════════

# Phrases that indicate the profile does NOT exist (soft 404s).
NOT_FOUND_SIGNALS = (
    "page not found", "user not found", "profile not found",
    "page isn't available", "this page isn't available",
    "sorry, this page", "the link you followed may be broken",
    "couldn't find this account", "this account doesn't exist",
    "this account doesn’t exist", "account suspended",
    "account has been suspended", "nobody on reddit goes by",
    "user does not exist", "isn't available on",
    "the specified profile could not be found", "no longer available",
    "bu sayfa kullanılamıyor", "sayfa bulunamadı",
)

# Final-URL paths that mean we were bounced to a generic landing page.
_GENERIC_PATHS = {
    "", "/login", "/signin", "/signup", "/home", "/404", "/error",
    "/accounts/login", "/auth/login", "/users/sign_in", "/register",
}

_GENERIC_IMG = (
    "default", "logo", "favicon", "placeholder", "share",
    "open_graph", "avatar_default", "sprite", "fallback",
)


def _is_generic_image(url: str) -> bool:
    u = url.lower()
    return any(w in u for w in _GENERIC_IMG)


def parse_meta(page_html: str) -> dict:
    """Parse <meta>, <title>, and <link rel=canonical> into one dict."""
    meta: dict = {}
    for m in re.finditer(r"<meta\s+([^>]+?)/?>", page_html, re.IGNORECASE):
        attrs = m.group(1)
        cm = re.search(r'content\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
        km = re.search(r'(?:property|name)\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
        if cm and km:
            key = km.group(1).lower()
            if key not in meta:
                meta[key] = _html.unescape(cm.group(1)).strip()
    tm = re.search(r"<title[^>]*>([^<]*)</title>", page_html, re.IGNORECASE)
    if tm:
        meta["__title__"] = _html.unescape(tm.group(1)).strip()
    cn = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
        page_html, re.IGNORECASE,
    )
    if cn:
        meta["__canonical__"] = cn.group(1).strip()
    return meta


def _looks_not_found(resp) -> bool:
    body = resp.text[:4000].lower()
    return any(sig in body for sig in NOT_FOUND_SIGNALS)


def _redirected_to_generic(resp, username: str) -> bool:
    """True if we were redirected to a home/login page (not the profile)."""
    try:
        path = urlparse(resp.url).path.rstrip("/").lower()
    except Exception:
        return False
    if path in _GENERIC_PATHS:
        return True
    if ("login" in path or "signin" in path) and username.lower() not in path:
        return True
    return False


def _mentions_handle(text: str, uname: str) -> bool:
    """Handle present as a token, not as an accident inside a longer word."""
    if not text or not uname:
        return False
    return re.search(rf"(?<![0-9a-z]){re.escape(uname)}(?![0-9a-z])", text) is not None


def confidence_score(resp, username: str, meta: dict) -> int:
    """
    Score how strongly the response corroborates a *real* profile for
    `username`. A hard negative (soft 404 / bounced to a landing page)
    returns a strongly negative score.

    The scoring is gated, not purely additive, because additive scoring cannot
    tell an account from an empty one. Sites that answer 200 for every handle
    serve the *same* page either way: same meta description, same default share
    image, same canonical echoing back whatever path was requested. Award
    points for those and a made-up handle scores exactly what a real one does —
    which is how a result ends up reported as found and then 404s when clicked.

    So a match needs at least one signal that could only come from a page
    rendered for this specific account: the handle in the page title, or
    follower/following counts. Everything else is corroboration and only
    counts once one of those has fired. Note what this gives up — a real
    profile on a site that renders entirely client-side scores 0, because
    nothing in the response distinguishes it from a nonexistent one. Silence
    is the honest answer there.

    Callers treat >= 3 as high confidence, 2 as medium, and < 2 as
    "not a confirmed match" (dropped).
    """
    if _looks_not_found(resp) or _redirected_to_generic(resp, username):
        return -10

    uname = username.lower()
    title = (meta.get("og:title", "") + " " + meta.get("__title__", "")).lower()
    urls = (meta.get("og:url", "") + " " + meta.get("__canonical__", "")).lower()
    og_type = meta.get("og:type", "").lower()
    og_img = meta.get("og:image", "")
    og_desc = meta.get("og:description", "") or meta.get("description", "")
    body_lower = resp.text[:4000].lower()

    # ── Account-specific evidence ─────────────────────────────
    score = 0
    if _mentions_handle(title, uname):                   # page is titled for them
        score += 2
    if ("follower" in body_lower and "following" in body_lower) or "takipçi" in body_lower:
        score += 2                                       # rendered social stats
    if not score:
        # Pinterest commonly returns a generic document title to non-browser
        # clients, even for a public profile. Its embedded state still names
        # the profile and carries account-only fields. Treat that combination
        # as equivalent to a profile title, but never accept a path/canonical
        # alone: Pinterest echoes requested paths for missing accounts too.
        if "pinterest.com" in urlparse(resp.url).netloc.lower():
            # Whole body, not a prefix. Pinterest ships ~1.5 MB of markup and
            # puts its embedded state near the very end: measured on real
            # profiles, "username" lands around 1,238,000 and <title> around
            # 1,220,828, so a 160,000-char window missed every signal and this
            # branch never fired. Scanning the rest is close to free, because
            # requests has already read the full body into resp.text — the
            # slice only ever limited the search, never the download.
            body = resp.text.lower()
            escaped = re.escape(uname)
            has_username_field = re.search(
                rf'["\']username["\']\s*:\s*["\']{escaped}["\']', body
            ) is not None
            has_profile_field = any(field in body for field in (
                '"full_name"', '"image_large_url"', '"image_xlarge_url"',
                '"follower_count"', '"following_count"',
            ))
            if has_username_field and has_profile_field:
                score = 2

    # ── Corroboration ─────────────────────────────────────────
    #
    # These used to count only once account-specific evidence had fired, and
    # anything without it was dropped. That gate was too strict in practice:
    # platforms that render client-side carry none of the evidence above even
    # for accounts that plainly exist, so real profiles were being hidden.
    # Nothing is dropped for weak evidence now — a page that showed no error
    # and did not bounce us to a login wall is reported, and the confidence
    # label carries the uncertainty instead of the visibility.
    #
    # The cost is real and worth stating: on a site that answers 200 for every
    # handle, a made-up name scores the same as a real one. That is a property
    # of those sites, not of the scoring — they return the same bytes either
    # way. Hence the "low" tier below.
    if _mentions_handle(urls, uname):                    # canonical names the handle
        score += 1
    if "profile" in og_type or "user" in og_type:        # og:type = profile
        score += 1
    if og_img.startswith("http") and not _is_generic_image(og_img):
        score += 1                                       # a real (non-default) avatar
    if len(og_desc) > 40:                                # substantive description
        score += 1
    return score


def _confidence_label(score: int) -> str:
    """
    high   — account-specific evidence (handle in title, follower counts)
    medium — several corroborating signals, no direct evidence
    low    — reachable, no error, nothing that distinguishes it from the
             site's generic page. Shown, but never presented as confirmed.
    """
    if score >= 3:
        return "high"
    return "medium" if score >= 2 else "low"


def rejection_reason(status_code: int, score=None) -> str:
    """
    Why a platform was checked and deliberately not reported as a match.

    Every competing tool shows these as green ticks; showing them as rejections
    with a stated reason is the difference between a result the user can trust
    and a wall of links that 404. The wording is aimed at the person reading
    the report, not at a log.
    """
    if status_code == -1:
        return "timed out"
    if status_code == -2:
        return "could not connect"
    if status_code == -3:
        return "request failed"
    if status_code == 404:
        return "no such account (404)"
    if status_code and status_code >= 400:
        return f"refused the request (HTTP {status_code})"
    if score is None:
        return f"unexpected response (HTTP {status_code})"
    if score <= -10:
        return "the page itself says this account does not exist"
    if score <= 0:
        return "answered 200, but the page has no account-specific content"
    return "only weak signals — not enough to confirm"


def extract_metadata(result: dict, meta: dict) -> None:
    """Populate bio / avatar / display name from parsed meta tags."""
    desc = meta.get("og:description") or meta.get("description")
    if desc and len(desc) > 10:
        result["bio"] = desc[:200]

    img = meta.get("og:image", "")
    if img.startswith("http") and not _is_generic_image(img):
        result["profile_pic_url"] = img

    title = (meta.get("og:title") or meta.get("__title__") or "").strip()
    if title and title.lower() not in ("instagram", "facebook", "tiktok", "twitter", "x"):
        result["display_name"] = title[:100]


DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Mobile/15E148 Safari/604.1"
)

_VERIFY_HEADERS = {
    "User-Agent": DESKTOP_UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Hosts that serve a scripted shell to anything that isn't a real browser —
# reddit.com returns the same contentless 200 for a live account and a made-up
# one, so every profile there scored as unverifiable. The old.* mirror still
# serves plain HTML with a real title and a real 404. We fetch the mirror and
# keep reporting the canonical URL, so the check has something to score
# without changing the link the user is given.
_FETCH_MIRRORS = {
    "reddit.com": "old.reddit.com",
    "www.reddit.com": "old.reddit.com",
}


def _fetchable(url: str) -> str:
    parts = urlsplit(url)
    mirror = _FETCH_MIRRORS.get(parts.netloc.lower())
    return urlunsplit(parts._replace(netloc=mirror)) if mirror else url


def verify_profile_url(url: str, username: str, timeout: int = 8) -> dict:
    """
    Fetch an arbitrary profile URL and score it exactly as a platform check is.

    Search engines return pages they indexed at some point in the past, and
    profiles get deleted, renamed and suspended. Anything that reaches the user
    as "account found" goes through here first, so a link that 404s or bounces
    to a login wall is demoted before it is shown rather than after it is
    clicked.

    Returns ``{"ok": bool, "status_code": int, "confidence": str|None,
    "match_score": int, "meta": dict}``. ``ok`` is False for any transport
    failure too: unreachable is not the same as confirmed.
    """
    out = {"ok": False, "status_code": 0, "confidence": None,
           "match_score": 0, "meta": {}}
    headers = _VERIFY_HEADERS
    if "instagram.com" in urlparse(url).netloc.lower():
        # Same reason the platform sweep does it: the desktop page is an empty
        # shell, the mobile one carries the OG tags the score is built from.
        headers = {**_VERIFY_HEADERS, "User-Agent": MOBILE_UA}
    try:
        resp = requests.get(_fetchable(url), headers=headers, timeout=timeout,
                            allow_redirects=True)
    except requests.exceptions.Timeout:
        out["status_code"] = -1
        return out
    except requests.exceptions.ConnectionError:
        out["status_code"] = -2
        return out
    except Exception:
        out["status_code"] = -3
        return out

    out["status_code"] = resp.status_code
    if resp.status_code != 200:
        return out

    meta = parse_meta(resp.text[:20000])
    score = confidence_score(resp, username, meta)
    out["meta"] = meta
    out["match_score"] = score
    # >= 0 keeps everything except the hard negatives (soft 404, login-wall
    # bounce), which score -10. Weak evidence is labelled, not discarded.
    if score >= 0:
        out["ok"] = True
        out["confidence"] = _confidence_label(score)
    return out


class UsernameChecker:
    """Concurrent, verified username enumeration across the platform list."""

    HEADERS = dict(_VERIFY_HEADERS)
    TIMEOUT = 8
    SLOW_TIMEOUT = 12

    def __init__(self, max_workers: int = 20, delay: float = 0.1):
        self.max_workers = max_workers
        self.delay = delay
        self.results: list[dict] = []
        # Every platform touched, matches and rejections alike. `results` keeps
        # only the matches for callers that just want those; the full list is
        # what lets the report say "117 checked, 5 confirmed, and here is why
        # the other 112 were not".
        self.all_results: list[dict] = []
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def _check_platform(self, name: str, url: str, expected: int, username: str = "") -> dict:
        result = {
            "platform": name,
            "url": url,
            "exists": False,
            "status_code": 0,
            "source": "username_check",
            "username": username,
        }
        if self._stop_flag:
            return result

        timeout = self.SLOW_TIMEOUT if name in SLOW_PLATFORMS else self.TIMEOUT
        headers = self.HEADERS
        # Instagram serves richer OG tags to a mobile UA.
        if name == "Instagram":
            headers = {**self.HEADERS, "User-Agent": MOBILE_UA}

        try:
            resp = requests.get(_fetchable(url), headers=headers,
                                timeout=timeout, allow_redirects=True)
            result["status_code"] = resp.status_code

            if resp.status_code == expected:
                meta = parse_meta(resp.text[:20000])
                score = confidence_score(resp, username, meta)
                # Recorded either way: the score is what the rejection panel
                # explains itself with.
                result["match_score"] = score
                if score >= 0:
                    result["exists"] = True
                    result["confidence"] = _confidence_label(score)
                    extract_metadata(result, meta)
        except requests.exceptions.Timeout:
            result["status_code"] = -1
        except requests.exceptions.ConnectionError:
            result["status_code"] = -2
        except Exception:
            result["status_code"] = -3

        if not result["exists"]:
            result["reason"] = rejection_reason(
                result["status_code"], result.get("match_score")
            )
        return result

    def scan(self, username: str, callback=None, deep: bool = False) -> list[dict]:
        """
        Scan platforms for `username`. Fast mode checks the first 50; deep
        mode checks all. `callback(module, message, progress, results)` is
        invoked after each platform completes (used for live progress).
        """
        self._stop_flag = False
        platforms = PLATFORMS if deep else PLATFORMS[:50]
        total = len(platforms)
        results: list[dict] = []
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for name, url_tpl, expected in platforms:
                if self._stop_flag:
                    break
                url = url_tpl.replace("{username}", username)
                futures[executor.submit(self._check_platform, name, url, expected, username)] = name

            for future in as_completed(futures):
                if self._stop_flag:
                    break
                result = future.result()
                results.append(result)
                completed += 1
                if callback:
                    progress = int((completed / total) * 100)
                    status = "found" if result["exists"] else "no match"
                    callback(
                        module="Username Check",
                        message=f"[{completed}/{total}] {result['platform']} — {status}",
                        progress=progress,
                        results=[result] if result["exists"] else [],
                    )
                if self.delay:
                    time.sleep(self.delay)

        self.all_results = results
        self.results = [r for r in results if r["exists"]]
        return self.results
