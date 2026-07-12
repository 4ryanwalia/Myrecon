"""
╔══════════════════════════════════════════════════════════════╗
║  Username Checker — Multi-Platform Enumeration Engine       ║
║  Checks 120+ platforms via HTTP HEAD/GET with threading     ║
║  Platform-specific validators for SPA sites (IG, FB, etc.)  ║
╚══════════════════════════════════════════════════════════════╝
"""

import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# ──────────────────────────────────────────────────────────────
#  Platform database:  (name, url_template, expected_status)
#  {username} is dynamically replaced at runtime.
# ──────────────────────────────────────────────────────────────

PLATFORMS: list[tuple[str, str, int]] = [
    # ── Social Media ──────────────────────────────────────────
    ("Twitter / X",       "https://x.com/{username}",                            200),
    ("Instagram",         "https://www.instagram.com/{username}/",                200),
    ("Facebook",          "https://www.facebook.com/{username}",                 200),
    ("TikTok",            "https://www.tiktok.com/@{username}",                  200),
    ("Snapchat",          "https://www.snapchat.com/add/{username}",             200),
    ("Tumblr",            "https://{username}.tumblr.com",                       200),
    ("Pinterest",         "https://www.pinterest.com/{username}/",               200),
    ("Flickr",            "https://www.flickr.com/people/{username}/",           200),
    ("VK",                "https://vk.com/{username}",                           200),
    ("Mastodon",          "https://mastodon.social/@{username}",                 200),
    ("Threads",           "https://www.threads.net/@{username}",                 200),
    ("Bluesky",           "https://bsky.app/profile/{username}.bsky.social",     200),

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
    ("Kaggle",            "https://www.kaggle.com/{username}",                   200),
    ("npm",               "https://www.npmjs.com/~{username}",                   200),
    ("PyPI",              "https://pypi.org/user/{username}/",                   200),
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
    ("Odysee",            "https://odysee.com/@{username}",                      200),
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
    ("Roblox",            "https://www.roblox.com/user.aspx?username={username}",200),
    ("Osu!",              "https://osu.ppy.sh/users/{username}",                 200),
    ("Minecraft",         "https://namemc.com/profile/{username}",               200),
    ("Fortnite Tracker",  "https://fortnitetracker.com/profile/all/{username}",  200),
    ("Xbox Gamertag",     "https://xboxgamertag.com/search/{username}",          200),

    # ── Photo / Art ───────────────────────────────────────────
    ("500px",             "https://500px.com/p/{username}",                      200),
    ("DeviantArt",        "https://www.deviantart.com/{username}",               200),
    ("ArtStation",        "https://www.artstation.com/{username}",               200),
    ("Unsplash",          "https://unsplash.com/@{username}",                    200),
    ("Imgur",             "https://imgur.com/user/{username}",                   200),
    ("VSCO",             "https://vsco.co/{username}/gallery",                   200),
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
    ("GitHub Gist",       "https://gist.github.com/{username}",                  200),

    # ── Other Platforms ───────────────────────────────────────
    ("Linktree",          "https://linktr.ee/{username}",                        200),
    ("Carrd",             "https://{username}.carrd.co",                         200),
    ("Bio.link",          "https://bio.link/{username}",                         200),
    ("Beacons",           "https://beacons.ai/{username}",                       200),
    ("Gravatar",          "https://gravatar.com/{username}",                     200),
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
    ("Instructables",     "https://www.instructables.com/member/{username}/",     200),
    ("Hackaday",          "https://hackaday.io/{username}",                      200),
    ("Goodreads",         "https://www.goodreads.com/{username}",                200),
    ("MyAnimeList",       "https://myanimelist.net/profile/{username}",           200),
    ("Letterboxd",        "https://letterboxd.com/{username}/",                  200),
    ("Trakt",             "https://trakt.tv/users/{username}",                   200),
    ("Duolingo",          "https://www.duolingo.com/profile/{username}",          200),
    ("Codecademy",        "https://www.codecademy.com/profiles/{username}",       200),
    ("FreeCodeCamp",      "https://www.freecodecamp.org/{username}",             200),
    ("HackerOne",         "https://hackerone.com/{username}",                    200),
    ("BugCrowd",          "https://bugcrowd.com/{username}",                     200),
]

TOTAL_PLATFORMS = len(PLATFORMS)


# ──────────────────────────────────────────────────────────────
#  Platform-Specific Validators
#  These handle SPA sites that return 200 for everything
# ──────────────────────────────────────────────────────────────

def _validate_instagram(resp, username: str) -> bool:
    """
    Instagram returns 200 for ALL URLs (login wall).
    Strategy: Instagram shows specific error text for non-existent profiles.
    If we DON'T see that error, the profile likely exists.
    Uses Turkish locale (?hl=tr) to get richer meta tags.
    """
    body = resp.text[:15000]
    body_lower = body.lower()

    # ── Negative signals: profile does NOT exist ─────────────
    not_found_signals = [
        "sorry, this page isn't available",
        "this page isn't available",
        "the link you followed may be broken",
        "page not found",
        "user not found",
        "bu sayfa kullanılamıyor",          # Turkish: "this page is unavailable"
        "sayfa bulunamadı",                 # Turkish: "page not found"
    ]
    for sig in not_found_signals:
        if sig in body_lower:
            return False

    # ── Strong positive signals ──────────────────────────────
    # og:description with follower counts = definitely real
    if "follower" in body_lower and "following" in body_lower:
        return True
    # Turkish follower text
    if "takipçi" in body_lower and "takip" in body_lower:
        return True

    # Username appears in page meta/JSON data
    positive_signals = [
        f'"username":"{username}"',
        f'"username": "{username}"',
        f"@{username}",
        "edge_followed_by",
        "is_private",
        "biography",
        "profile_pic_url",
        "full_name",
        "external_url",
        "is_verified",
        "media_count",
        '"user":',
    ]
    for sig in positive_signals:
        if sig.lower() in body_lower:
            return True

    # og:title contains the username
    og_title_match = re.search(
        r'content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']og:title["\']',
        body, re.IGNORECASE
    )
    if not og_title_match:
        og_title_match = re.search(
            r'(?:property|name)=["\']og:title["\'][^>]*content=["\']([^"\']*)["\']',
            body, re.IGNORECASE
        )
    if og_title_match:
        title = og_title_match.group(1).lower()
        if username.lower() in title:
            return True

    # og:description exists and has content (real profiles always have this)
    og_desc_match = re.search(
        r'(?:property|name)=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']',
        body, re.IGNORECASE
    )
    if not og_desc_match:
        og_desc_match = re.search(
            r'content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']og:description["\']',
            body, re.IGNORECASE
        )
    if og_desc_match:
        desc = og_desc_match.group(1).strip()
        if len(desc) > 20 and ("instagram" not in desc.lower() or username.lower() in desc.lower()):
            return True

    # ── If page is large and no error found → likely exists ──
    if len(resp.text) > 3000:
        return True

    # Small/empty page with no positive signals → not found
    return False


def _validate_facebook(resp, username: str) -> bool:
    """Facebook also returns 200 with login walls for non-existent users."""
    body_lower = resp.text[:5000].lower()

    # Facebook login wall
    if "you must log in to continue" in body_lower:
        return False
    if "this page isn't available" in body_lower:
        return False
    if "this content isn't available" in body_lower:
        return False

    # Real profile indicators
    if f"/{username}" in body_lower and ("profile" in body_lower or "timeline" in body_lower):
        return True

    # Check og:title for username
    og_title = re.search(
        r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']*)["\']',
        resp.text[:5000], re.IGNORECASE
    )
    if og_title and username.lower() in og_title.group(1).lower():
        return True

    return True  # Facebook is more reliable with status codes


def _validate_tiktok(resp, username: str) -> bool:
    """TikTok returns 200 with different page content for invalid users."""
    body_lower = resp.text[:5000].lower()

    if "couldn't find this account" in body_lower:
        return False
    if "this account was banned" in body_lower:
        return False
    if '"statusCode":10202' in resp.text[:5000]:
        return False

    # Real profile signals
    if '"uniqueId"' in resp.text[:5000] or '"nickname"' in resp.text[:5000]:
        return True

    # Check og:title
    og_title = re.search(
        r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']*)["\']',
        resp.text[:5000], re.IGNORECASE
    )
    if og_title:
        title = og_title.group(1).lower()
        if username.lower() in title or f"@{username.lower()}" in title:
            return True
        if "tiktok" == title.strip():
            return False

    return True


def _validate_twitter(resp, username: str) -> bool:
    """Twitter/X returns 200 but may show 'This account doesn't exist'."""
    body_lower = resp.text[:5000].lower()

    if "this account doesn't exist" in body_lower:
        return False
    if "account is suspended" in body_lower:
        return False
    if "something went wrong" in body_lower and username.lower() not in body_lower:
        return False

    return True


def _validate_linkedin(resp, username: str) -> bool:
    """LinkedIn aggressively redirects to login — check for authwall."""
    body_lower = resp.text[:5000].lower()

    if "authwall" in body_lower or "join linkedin" in body_lower:
        # LinkedIn shows authwall even for real profiles — check og:title
        og_title = re.search(
            r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']*)["\']',
            resp.text[:5000], re.IGNORECASE
        )
        if og_title:
            title = og_title.group(1).lower()
            if username.lower() in title or "linkedin" not in title:
                return True
        return False

    return True


# Registry of platform-specific validators
PLATFORM_VALIDATORS = {
    "Instagram": _validate_instagram,
    "Facebook": _validate_facebook,
    "TikTok": _validate_tiktok,
    "Twitter / X": _validate_twitter,
    "LinkedIn": _validate_linkedin,
}

# Platforms that need longer timeout (SPAs, slow APIs)
SLOW_PLATFORMS = {"Instagram", "Facebook", "TikTok", "LinkedIn", "Threads"}


class UsernameChecker:
    """
    Performs concurrent HTTP checks against 120+ platforms to detect
    whether a username has a registered profile.
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    TIMEOUT = 8  # seconds
    SLOW_TIMEOUT = 12  # for SPA platforms

    def __init__(self, max_workers: int = 20, delay: float = 0.1):
        self.max_workers = max_workers
        self.delay = delay
        self.results: list[dict] = []
        self._stop_flag = False

    def stop(self):
        """Signal the checker to stop scanning."""
        self._stop_flag = True

    def _check_platform(self, name: str, url: str, expected: int, username: str = "") -> dict:
        """Check a single platform for the existence of the username."""
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

        # Instagram requires mobile UA to bypass login wall
        headers = self.HEADERS
        if name == "Instagram":
            headers = {
                **self.HEADERS,
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/16.6 Mobile/15E148 Safari/604.1"
                ),
            }

        try:
            resp = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
            )
            result["status_code"] = resp.status_code

            if resp.status_code == expected:
                # ── Platform-specific validation ─────────────
                validator = PLATFORM_VALIDATORS.get(name)
                if validator:
                    result["exists"] = validator(resp, username)
                else:
                    # Generic soft-404 detection for standard platforms
                    body_lower = resp.text[:2000].lower()
                    soft_404_signals = [
                        "page not found",
                        "user not found",
                        "profile not found",
                        "doesn't exist",
                        "does not exist",
                        "no user",
                        "404",
                        "this page isn't available",
                        "sorry, this page",
                        "account suspended",
                        "account has been suspended",
                    ]
                    is_soft_404 = any(sig in body_lower for sig in soft_404_signals)
                    result["exists"] = not is_soft_404

                # ── Extract basic metadata from the page ─────
                if result["exists"]:
                    self._extract_basic_metadata(result, resp, username)

        except requests.exceptions.Timeout:
            result["status_code"] = -1  # timeout
        except requests.exceptions.ConnectionError:
            result["status_code"] = -2  # connection error
        except Exception:
            result["status_code"] = -3  # unknown error

        return result

    def _extract_basic_metadata(self, result: dict, resp, username: str):
        """Extract basic bio/pic from meta tags during the initial check."""
        try:
            html = resp.text[:8000]

            # Extract og:description
            desc_match = re.search(
                r'<meta\s+[^>]*?content=["\']([^"\']*)["\'][^>]*?'
                r'(?:property|name)=["\']og:description["\']',
                html, re.IGNORECASE
            )
            if not desc_match:
                desc_match = re.search(
                    r'<meta\s+[^>]*?(?:property|name)=["\']og:description["\']'
                    r'[^>]*?content=["\']([^"\']*)["\']',
                    html, re.IGNORECASE
                )
            if desc_match:
                desc = desc_match.group(1).strip()
                if desc and len(desc) > 10:
                    result["bio"] = desc[:200]

            # Extract og:image for profile pic
            img_match = re.search(
                r'<meta\s+[^>]*?content=["\']([^"\']*)["\'][^>]*?'
                r'(?:property|name)=["\']og:image["\']',
                html, re.IGNORECASE
            )
            if not img_match:
                img_match = re.search(
                    r'<meta\s+[^>]*?(?:property|name)=["\']og:image["\']'
                    r'[^>]*?content=["\']([^"\']*)["\']',
                    html, re.IGNORECASE
                )
            if img_match:
                pic_url = img_match.group(1).strip()
                if pic_url and pic_url.startswith("http"):
                    # Skip generic/default images
                    skip_words = ["default", "logo", "favicon", "placeholder", "share", "open_graph"]
                    if not any(w in pic_url.lower() for w in skip_words):
                        result["profile_pic_url"] = pic_url

            # Extract og:title for display name
            title_match = re.search(
                r'<meta\s+[^>]*?content=["\']([^"\']*)["\'][^>]*?'
                r'(?:property|name)=["\']og:title["\']',
                html, re.IGNORECASE
            )
            if not title_match:
                title_match = re.search(
                    r'<meta\s+[^>]*?(?:property|name)=["\']og:title["\']'
                    r'[^>]*?content=["\']([^"\']*)["\']',
                    html, re.IGNORECASE
                )
            if title_match:
                title = title_match.group(1).strip()
                if title and title.lower() not in ("", "instagram", "facebook", "tiktok"):
                    result["display_name"] = title[:100]

        except Exception:
            pass

    def scan(self, username: str, callback=None, deep: bool = False) -> list[dict]:
        """
        Scan all platforms for the given username.
        In fast mode, check the first 50 platforms. Deep mode checks all.
        """
        self._stop_flag = False
        platforms = PLATFORMS if deep else PLATFORMS[:50]
        total = len(platforms)
        results = []
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for name, url_tpl, expected in platforms:
                if self._stop_flag:
                    break
                url = url_tpl.replace("{username}", username)
                future = executor.submit(self._check_platform, name, url, expected, username)
                futures[future] = (name, url)

            for future in as_completed(futures):
                if self._stop_flag:
                    break
                result = future.result()
                results.append(result)
                completed += 1

                if callback:
                    progress = int((completed / total) * 100)
                    status = "✓ FOUND" if result["exists"] else "✗ Not found"
                    callback(
                        module="Username Check",
                        message=f"[{completed}/{total}] {result['platform']} — {status}",
                        progress=progress,
                        results=[result] if result["exists"] else [],
                    )

                time.sleep(self.delay)

        self.results = [r for r in results if r["exists"]]
        return self.results
