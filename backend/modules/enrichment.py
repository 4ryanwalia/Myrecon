"""
╔══════════════════════════════════════════════════════════════╗
║  Profile Enrichment Engine                                  ║
║  Fetches bio, followers, profile pic from found profiles    ║
║  Supports: Instagram, GitHub, Reddit, Gravatar, and more    ║
╚══════════════════════════════════════════════════════════════╝
"""

import re
import requests
import time
import hashlib
import html
from typing import Optional

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Mobile Safari UA bypasses Instagram's login wall
MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.6 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 8


# ──────────────────────────────────────────────────────────────
#  Image Downloader
# ──────────────────────────────────────────────────────────────

def _download_image(url: str, timeout: int = 6) -> bytes:
    """Download an image and return raw bytes."""
    if not url or not url.startswith("http"):
        return b""
    try:
        # Skip server-side download for Instagram CDN to avoid 403s and timeouts.
        # The frontend will render the image directly using referrerpolicy="no-referrer".
        if "cdninstagram" in url or "scontent" in url:
            return b""
            
        resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
        if resp.status_code == 200 and len(resp.content) < 5_000_000:
            return resp.content
    except Exception:
        pass
    return b""


# ──────────────────────────────────────────────────────────────
#  Instagram Enrichment — with validation, logging & fallbacks
# ──────────────────────────────────────────────────────────────

import logging
_ig_log = logging.getLogger("enrichment.instagram")


def _validate_ig_username(username: str) -> bool:
    """Instagram usernames: 1-30 chars, alphanumeric + periods + underscores."""
    return bool(re.match(r'^[a-zA-Z0-9._]{1,30}$', username))


def _parse_ig_meta_tags(page_html: str) -> dict:
    """Extract all <meta> property→content pairs, with HTML-entity decoding."""
    meta_tags = re.findall(r'<meta\s+([^>]+?)/?>', page_html, re.IGNORECASE)
    meta_map = {}
    for tag_attrs in meta_tags:
        content_m = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
        if not content_m:
            continue
        content = html.unescape(content_m.group(1))
        prop_m = re.search(r'(?:property|name)\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
        if not prop_m:
            continue
        prop = prop_m.group(1).lower()
        if prop not in meta_map:
            meta_map[prop] = content
    return meta_map


def _detect_ig_account_status(page_html: str, meta_map: dict) -> str:
    """
    Detect account status from the page content.
    Returns: 'exists', 'not_found', 'private', 'restricted', or 'unknown'.
    """
    body_lower = page_html[:15000].lower()

    # ── Account does not exist ────────────────────────────────
    not_found_signals = [
        "sorry, this page isn't available",
        "this page isn't available",
        "the link you followed may be broken",
        "page not found",
        "user not found",
        "bu sayfa kullanılamıyor",
        "sayfa bulunamadı",
    ]
    for sig in not_found_signals:
        if sig in body_lower:
            return "not_found"

    # ── Account exists (has og metadata with follower info) ───
    desc = meta_map.get("og:description", "")
    if "follower" in desc.lower() and "following" in desc.lower():
        return "exists"

    # ── Page is very small / has no meaningful content ────────
    if len(page_html) < 5000:
        return "not_found"

    return "unknown"


def _extract_ig_data_from_meta(meta_map: dict, data: dict) -> None:
    """Populate `data` dict from Instagram OG meta tags."""

    # Profile pic from og:image (must be scontent CDN, not the IG logo)
    pic = meta_map.get("og:image", "")
    if pic and "scontent" in pic:
        data["profile_pic_url"] = pic
        # Skip server-side download — frontend renders via referrerpolicy="no-referrer"
        data["profile_pic_data"] = b""

    # Parse og:description → followers / following / posts / bio
    desc = meta_map.get("og:description", "")
    if desc:
        followers_m = re.search(r'([\d,.]+[KMkm]?)\s+Follower', desc)
        following_m = re.search(r'([\d,.]+[KMkm]?)\s+Following', desc)
        posts_m     = re.search(r'([\d,.]+[KMkm]?)\s+Post', desc)
        if followers_m:
            data["followers"] = _parse_count(followers_m.group(1))
        if following_m:
            data["following"] = _parse_count(following_m.group(1))
        if posts_m:
            data["posts"] = _parse_count(posts_m.group(1))
        bio_m = re.search(r'Posts?\s*[-\u2013\u2014]\s*(.*)', desc)
        if bio_m:
            data["bio"] = bio_m.group(1).strip().rstrip('"')

    # Display name from og:title  ("Aryan walia (@4ryanwalia) …")
    title = meta_map.get("og:title", "")
    if title:
        name_m = re.match(r'^(.*?)\s*[\(\[]?@', title)
        if name_m:
            data["display_name"] = name_m.group(1).strip()

    # Also check the plain 'description' meta (has the actual user-written bio)
    # Format: '67 Followers, 93 Following, 0 Posts - Aryan walia (@user) on Instagram: "bio text"'
    # This is more accurate than og:description which just says "See Instagram photos..."
    plain_desc = meta_map.get("description", "")
    if plain_desc:
        bio_m = re.search(r'on Instagram:\s*["\u201c](.+?)["\u201d]', plain_desc)
        if bio_m:
            data["bio"] = bio_m.group(1).strip()


def _enrich_instagram(username: str) -> dict:
    """
    Fetch public Instagram profile data with validation, logging, and fallbacks.

    Strategy (in order):
        1. Public page meta tags (mobile UA → OG tags served by Instagram for SEO)
        2. Session-based web API endpoint
        3. Instaloader library (if installed)

    Handles:
        - Invalid username format
        - Account does not exist
        - Account is private (limited data still available via OG tags)
        - Temporary unavailability / rate-limiting
    """
    data = {"platform": "Instagram", "username": username}

    # ── Step 0: Validate username format ─────────────────────
    if not _validate_ig_username(username):
        _ig_log.warning("Invalid Instagram username format: %s", username)
        data["error"] = "Invalid username format"
        return data

    _ig_log.info("Enriching Instagram profile: %s", username)

    # ── Step 1: Public profile page (OG meta tags) ───────────
    #   Instagram serves <meta property="og:*"> tags to any HTTP client.
    #   These contain follower counts, bio excerpt, and profile picture URL.
    try:
        _ig_log.debug("Method 1: Fetching public page for %s", username)
        resp = requests.get(
            f"https://www.instagram.com/{username}/",
            headers={**MOBILE_HEADERS, "Accept": "text/html,application/xhtml+xml"},
            timeout=12,
        )

        if resp.status_code == 200:
            page_html = resp.text
            meta_map = _parse_ig_meta_tags(page_html)
            status = _detect_ig_account_status(page_html, meta_map)

            if status == "not_found":
                _ig_log.info("Instagram account '%s' does not exist", username)
                data["error"] = "Account not found"
                return data

            if status == "exists" or meta_map.get("og:image"):
                _extract_ig_data_from_meta(meta_map, data)

                has_data = data.get("bio") or data.get("profile_pic_url") or data.get("followers")
                if has_data:
                    _ig_log.info(
                        "Instagram data found for %s: followers=%s, has_pic=%s, has_bio=%s",
                        username,
                        data.get("followers", "N/A"),
                        bool(data.get("profile_pic_url")),
                        bool(data.get("bio")),
                    )
                    return data
                else:
                    _ig_log.debug("Method 1 returned no usable data for %s", username)
            else:
                _ig_log.debug(
                    "Account status for %s: %s (meta keys: %s)",
                    username, status, list(meta_map.keys()),
                )

        elif resp.status_code == 404:
            _ig_log.info("Instagram returned 404 for '%s'", username)
            data["error"] = "Account not found"
            return data
        elif resp.status_code == 429:
            _ig_log.warning("Instagram rate-limited (429) when fetching %s", username)
            data["error"] = "Rate limited — try again later"
        else:
            _ig_log.debug("Instagram returned HTTP %d for %s", resp.status_code, username)

    except requests.exceptions.Timeout:
        _ig_log.warning("Timeout fetching Instagram page for %s", username)
    except requests.exceptions.ConnectionError:
        _ig_log.warning("Connection error fetching Instagram for %s", username)
    except Exception as e:
        _ig_log.debug("Method 1 failed for %s: %s", username, e)

    # ── Step 2: Web API endpoint (session-based) ─────────────
    try:
        _ig_log.debug("Method 2: Trying web API for %s", username)
        s = requests.Session()
        s.headers.update(MOBILE_HEADERS)
        s.get("https://www.instagram.com/", timeout=8)
        time.sleep(0.5)

        csrf = s.cookies.get("csrftoken", "")
        s.headers.update({
            "X-CSRFToken": csrf,
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/{username}/",
            "Accept": "*/*",
        })
        r = s.get(
            f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            j = r.json()
            user = j.get("data", {}).get("user", {})
            if not user:
                user = j.get("graphql", {}).get("user", j.get("user", {}))
            if user:
                data["bio"] = user.get("biography", "") or ""
                data["display_name"] = user.get("full_name", "") or ""
                data["followers"] = user.get("edge_followed_by", {}).get("count", 0)
                data["following"] = user.get("edge_follow", {}).get("count", 0)
                data["posts"] = user.get("edge_owner_to_timeline_media", {}).get("count", 0)
                data["profile_pic_url"] = user.get("profile_pic_url_hd", user.get("profile_pic_url", ""))
                data["is_private"] = user.get("is_private", False)
                data["is_verified"] = user.get("is_verified", False)
                if data.get("profile_pic_url"):
                    data["profile_pic_data"] = _download_image(data["profile_pic_url"])
                if data.get("bio") or data.get("profile_pic_url"):
                    _ig_log.info("Method 2 succeeded for %s", username)
                    return data
        else:
            _ig_log.debug("Web API returned HTTP %d for %s", r.status_code, username)
    except Exception as e:
        _ig_log.debug("Method 2 failed for %s: %s", username, e)

    # ── Step 3: Instaloader library (if installed) ────────────
    try:
        import instaloader
        _ig_log.debug("Method 3: Trying instaloader for %s", username)
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)
        data["bio"] = profile.biography or ""
        data["display_name"] = profile.full_name or ""
        data["followers"] = profile.followers
        data["following"] = profile.followees
        data["posts"] = profile.mediacount
        data["profile_pic_url"] = profile.profile_pic_url or ""
        data["is_private"] = profile.is_private
        data["is_verified"] = profile.is_verified
        if data["profile_pic_url"]:
            data["profile_pic_data"] = _download_image(data["profile_pic_url"])
        _ig_log.info("Method 3 (instaloader) succeeded for %s", username)
        return data
    except ImportError:
        _ig_log.debug("Instaloader not installed, skipping Method 3")
    except Exception as e:
        _ig_log.debug("Method 3 failed for %s: %s", username, e)

    # ── All methods exhausted ────────────────────────────────
    if not data.get("error"):
        _ig_log.warning("Instagram data not found for %s (all methods failed)", username)
        data["error"] = "Data temporarily unavailable"

    return data


def _parse_count(s: str) -> int:
    """Parse '1,234' or '1.2K' or '3.5M' to int."""
    s = s.replace(",", "").strip()
    try:
        if s[-1].upper() == "K":
            return int(float(s[:-1]) * 1000)
        elif s[-1].upper() == "M":
            return int(float(s[:-1]) * 1000000)
        return int(float(s))
    except (ValueError, IndexError):
        return 0


# ──────────────────────────────────────────────────────────────
#  GitHub Enrichment (free API, no key needed)
# ──────────────────────────────────────────────────────────────

def _enrich_github(username: str) -> dict:
    data = {"platform": "GitHub", "username": username}
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}",
            headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/vnd.github.v3+json"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            j = resp.json()
            data["bio"] = j.get("bio", "") or ""
            data["display_name"] = j.get("name", "") or ""
            data["followers"] = j.get("followers", 0)
            data["following"] = j.get("following", 0)
            data["repos"] = j.get("public_repos", 0)
            data["location"] = j.get("location", "") or ""
            data["company"] = j.get("company", "") or ""
            data["profile_pic_url"] = j.get("avatar_url", "")
            data["blog"] = j.get("blog", "") or ""
            data["created_at"] = j.get("created_at", "")
            if data["profile_pic_url"]:
                data["profile_pic_data"] = _download_image(data["profile_pic_url"])
    except Exception:
        pass
    return data


# ──────────────────────────────────────────────────────────────
#  Reddit Enrichment
# ──────────────────────────────────────────────────────────────

def _enrich_reddit(username: str) -> dict:
    data = {"platform": "Reddit", "username": username}
    try:
        resp = requests.get(
            f"https://www.reddit.com/user/{username}/about.json",
            headers=HEADERS, timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            j = resp.json().get("data", {})
            data["bio"] = j.get("subreddit", {}).get("public_description", "") or ""
            data["display_name"] = j.get("subreddit", {}).get("title", "") or ""
            data["followers"] = j.get("subreddit", {}).get("subscribers", 0)
            data["karma"] = j.get("total_karma", 0)
            data["profile_pic_url"] = j.get("icon_img", "").split("?")[0]
            data["created_at"] = str(j.get("created_utc", ""))
            if data["profile_pic_url"]:
                data["profile_pic_data"] = _download_image(data["profile_pic_url"])
    except Exception:
        pass
    return data


# ──────────────────────────────────────────────────────────────
#  Gravatar Enrichment (works for any user via hash)
# ──────────────────────────────────────────────────────────────

def _enrich_gravatar(username: str) -> dict:
    data = {"platform": "Gravatar", "username": username}
    try:
        # Gravatar uses email hash — try username as-is first
        profile_url = f"https://en.gravatar.com/{username}.json"
        resp = requests.get(profile_url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            j = resp.json()
            entry = j.get("entry", [{}])[0]
            data["display_name"] = entry.get("displayName", "") or ""
            data["bio"] = entry.get("aboutMe", "") or ""
            data["profile_pic_url"] = entry.get("thumbnailUrl", "")
            if data["profile_pic_url"]:
                # Get high-res version
                data["profile_pic_url"] = data["profile_pic_url"].split("?")[0] + "?s=400"
                data["profile_pic_data"] = _download_image(data["profile_pic_url"])
    except Exception:
        pass
    return data


# ──────────────────────────────────────────────────────────────
#  Generic OG-tag scraper (fallback for any platform)
# ──────────────────────────────────────────────────────────────

def _enrich_from_og_tags(url: str) -> dict:
    """Extract bio and profile pic from OpenGraph/Twitter meta tags."""
    data = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return data

        html = resp.text  # scan full page — Pinterest puts OG tags 700KB+ deep

        # Step 1: Find ALL <meta ...> tags
        meta_tags = re.findall(r'<meta\s+([^>]+?)/?>', html, re.IGNORECASE)

        # Step 2: Parse each meta tag into a dict of attributes
        meta_map = {}  # property/name -> content
        for tag_attrs in meta_tags:
            # Extract content attribute
            content_m = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
            if not content_m:
                continue
            import html
            content = html.unescape(content_m.group(1))

            # Extract property or name attribute
            prop_m = re.search(r'(?:property|name)\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
            if not prop_m:
                continue
            prop = prop_m.group(1).lower()

            if prop not in meta_map:
                meta_map[prop] = content

        def _get(key: str) -> str:
            return meta_map.get(key, "")

        # Profile picture: og:image > twitter:image > twitter:image:src
        pic_url = _get("og:image") or _get("twitter:image") or _get("twitter:image:src")
        if pic_url and pic_url.startswith("http"):
            # Skip generic/default images
            skip_words = ["default", "logo", "favicon", "placeholder", "share", "open_graph"]
            is_generic = any(w in pic_url.lower() for w in skip_words)
            if not is_generic:
                data["profile_pic_url"] = pic_url
                data["profile_pic_data"] = _download_image(pic_url)

        # Bio: og:description > twitter:description > description
        bio = _get("og:description") or _get("twitter:description") or _get("description")
        if bio:
            data["bio"] = bio[:200]

        # Display name: og:title > twitter:title > <title> tag
        title = _get("og:title") or _get("twitter:title")
        if not title:
            m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
        if title:
            data["display_name"] = title[:100]

    except Exception:
        pass
    return data


# ──────────────────────────────────────────────────────────────
#  Twitter / X Enrichment (via syndication API — no auth needed)
# ──────────────────────────────────────────────────────────────

def _enrich_twitter(username: str) -> dict:
    data = {"platform": "Twitter / X", "username": username}
    try:
        # Twitter syndication API — public, no auth
        url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            html = resp.text
            # Extract display name from the timeline HTML
            name_m = re.search(r'data-testid="UserName"[^>]*>.*?<span[^>]*>([^<]+)</span>', html, re.DOTALL)
            if name_m:
                data["display_name"] = name_m.group(1).strip()
            # Extract bio
            bio_m = re.search(r'data-testid="UserDescription"[^>]*>([^<]+)', html)
            if bio_m:
                data["bio"] = bio_m.group(1).strip()[:200]
            # Try profile pic
            pic_m = re.search(r'src="(https://pbs\.twimg\.com/profile_images/[^"]+)"', html)
            if pic_m:
                data["profile_pic_url"] = pic_m.group(1)
                data["profile_pic_data"] = _download_image(data["profile_pic_url"])
    except Exception:
        pass

    # Fallback: OG tags from x.com
    if not data.get("bio") and not data.get("profile_pic_url"):
        try:
            og = _enrich_from_og_tags(f"https://x.com/{username}")
            for k, v in og.items():
                if v and not data.get(k):
                    data[k] = v
        except Exception:
            pass

    return data


# ──────────────────────────────────────────────────────────────
#  TikTok Enrichment (OG tag scraping)
# ──────────────────────────────────────────────────────────────

def _enrich_tiktok(username: str) -> dict:
    data = {"platform": "TikTok", "username": username}
    try:
        url = f"https://www.tiktok.com/@{username}"
        resp = requests.get(url, headers={
            **HEADERS,
            "Accept": "text/html,application/xhtml+xml",
        }, timeout=TIMEOUT)
        if resp.status_code == 200:
            html = resp.text[:10000]
            # Parse meta tags
            meta_tags = re.findall(r'<meta\s+([^>]+?)/?>',  html, re.IGNORECASE)
            meta_map = {}
            for tag_attrs in meta_tags:
                content_m = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
                if not content_m:
                    continue
                content = content_m.group(1)
                prop_m = re.search(r'(?:property|name)\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
                if not prop_m:
                    continue
                prop = prop_m.group(1).lower()
                if prop not in meta_map:
                    meta_map[prop] = content

            desc = meta_map.get("og:description", "")
            if desc:
                # TikTok descriptions have: "Follower, Likes. Bio text"
                followers_m = re.search(r'([\d,.]+[KMBkmb]?)\s+Follower', desc)
                likes_m = re.search(r'([\d,.]+[KMBkmb]?)\s+Like', desc)
                if followers_m:
                    data["followers"] = _parse_count(followers_m.group(1))
                if likes_m:
                    data["enriched_data"] = {"likes": _parse_count(likes_m.group(1))}
                # Bio is after the stats
                bio_m = re.search(r'Likes?\.\s*(.*)', desc)
                if bio_m:
                    data["bio"] = bio_m.group(1).strip()[:200]
                elif desc:
                    data["bio"] = desc[:200]

            title = meta_map.get("og:title", "")
            if title:
                name_m = re.match(r'^(.*?)\s*[\(\[]?@', title)
                if name_m:
                    data["display_name"] = name_m.group(1).strip()

            pic = meta_map.get("og:image", "")
            if pic and pic.startswith("http") and "tiktok" in pic:
                data["profile_pic_url"] = pic
                data["profile_pic_data"] = _download_image(pic)
    except Exception:
        pass
    return data


# ──────────────────────────────────────────────────────────────
#  LinkedIn Enrichment (OG tag based — no API needed)
# ──────────────────────────────────────────────────────────────

def _enrich_linkedin(username: str) -> dict:
    data = {"platform": "LinkedIn", "username": username}
    try:
        og = _enrich_from_og_tags(f"https://www.linkedin.com/in/{username}")
        for k, v in og.items():
            if v:
                data[k] = v
    except Exception:
        pass
    return data


# ──────────────────────────────────────────────────────────────
#  Pinterest Enrichment (parses embedded JSON for profile pic)
# ──────────────────────────────────────────────────────────────

def _enrich_pinterest(username: str) -> dict:
    """Pinterest og:image returns the default logo. Parse embedded JSON instead."""
    data = {"platform": "Pinterest", "username": username}
    try:
        resp = requests.get(
            f"https://www.pinterest.com/{username}/",
            headers=HEADERS, timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return data
        html = resp.text

        # Parse meta tags for bio/title
        meta_tags = re.findall(r'<meta\s+([^>]+?)/?>', html, re.IGNORECASE)
        meta_map = {}
        for tag_attrs in meta_tags:
            content_m = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
            if not content_m:
                continue
            content = content_m.group(1)
            prop_m = re.search(r'(?:property|name)\s*=\s*["\']([^"\']*)["\']', tag_attrs, re.IGNORECASE)
            if not prop_m:
                continue
            prop = prop_m.group(1).lower()
            if prop not in meta_map:
                meta_map[prop] = content

        desc = meta_map.get("og:description", "") or meta_map.get("description", "")
        if desc:
            data["bio"] = desc[:200]
        title = meta_map.get("og:title", "")
        if title:
            name_m = re.match(r'^(.*?)\s*\(', title)
            if name_m:
                data["display_name"] = name_m.group(1).strip()
            else:
                data["display_name"] = title.replace(" - Profile | Pinterest", "").strip()[:100]

        # Extract profile pic from embedded JSON (image_xlarge_url)
        pic_m = re.search(r'"image_xlarge_url"\s*:\s*"([^"]+)"', html)
        if not pic_m:
            pic_m = re.search(r'"image_large_url"\s*:\s*"([^"]+)"', html)
        if not pic_m:
            pic_m = re.search(r'"image_medium_url"\s*:\s*"([^"]+)"', html)
        if pic_m:
            pic_url = pic_m.group(1).replace("\\/", "/")
            if pic_url.startswith("http"):
                data["profile_pic_url"] = pic_url
                data["profile_pic_data"] = _download_image(pic_url)

        # Try to get follower count from JSON
        followers_m = re.search(r'"follower_count"\s*:\s*(\d+)', html)
        if followers_m:
            data["followers"] = int(followers_m.group(1))
        pins_m = re.search(r'"pin_count"\s*:\s*(\d+)', html)
        if pins_m:
            data["enriched_data"] = {"pins": int(pins_m.group(1))}

    except Exception:
        pass
    return data


# ──────────────────────────────────────────────────────────────
#  Platform Enricher Registry
# ──────────────────────────────────────────────────────────────

PLATFORM_ENRICHERS = {
    "Instagram":    _enrich_instagram,
    "GitHub":       _enrich_github,
    "Reddit":       _enrich_reddit,
    "Gravatar":     _enrich_gravatar,
    "Twitter / X":  _enrich_twitter,
    "TikTok":       _enrich_tiktok,
    "LinkedIn":     _enrich_linkedin,
    "Pinterest":    _enrich_pinterest,
}

# Platforms where we can try OG-tag scraping as fallback
OG_ENRICHABLE = {
    "Medium", "Dev.to", "Hashnode", "Behance", "Dribbble",
    "500px", "DeviantArt", "ArtStation", "Kaggle", "HackerRank",
    "LeetCode", "ProductHunt", "Linktree", "About.me",
    "SoundCloud", "Bandcamp", "Letterboxd", "Goodreads",
    "Twitch", "YouTube", "Threads",
    "Snapchat", "Steam", "Vimeo", "Kick", "Mastodon",
    "Bluesky", "Patreon", "Substack", "Ko-fi", "Buymeacoffee",
}


class ProfileEnricher:
    """Enriches found profiles with bio, followers, profile pictures."""

    def __init__(self, delay: float = 0.3):
        self.delay = delay
        self._stop = False

    def stop(self):
        self._stop = True

    def enrich(self, result: dict, callback=None) -> dict:
        """Enrich a single result with additional profile data."""
        if self._stop:
            return result

        platform = result.get("platform", "")
        username = result.get("username", "")

        if not username:
            url = result.get("url", "")
            parts = url.rstrip("/").split("/")
            username = parts[-1] if parts else ""
            username = username.lstrip("@")
            result["username"] = username

        # Try platform-specific enricher first
        enricher = PLATFORM_ENRICHERS.get(platform)
        if enricher and username:
            try:
                enriched = enricher(username)
                # Only update with non-empty values
                for k, v in enriched.items():
                    if v:
                        result[k] = v
                if callback:
                    has_data = bool(result.get("bio") or result.get("profile_pic_data"))
                    callback(
                        module="Enrichment",
                        message=f"Enriched {platform}: {username}" + (" [DATA FOUND]" if has_data else " [no data]"),
                        progress=0,
                        results=[],
                    )
            except Exception:
                pass
            time.sleep(self.delay)
            return result

        # For ALL other platforms: try OG-tag scraping from their URL
        url = result.get("url", "")
        if url and url.startswith("http"):
            try:
                og_data = _enrich_from_og_tags(url)
                for k, v in og_data.items():
                    if v:
                        result[k] = v
                if callback:
                    has_data = bool(result.get("bio") or result.get("profile_pic_data"))
                    callback(
                        module="Enrichment",
                        message=f"Scraped {platform}: {username}" + (" [DATA]" if has_data else " [no extra data]"),
                        progress=0,
                        results=[],
                    )
            except Exception:
                pass
            time.sleep(self.delay)

        return result

    def enrich_all(self, results: list[dict], callback=None) -> list[dict]:
        """Enrich all found profiles."""
        enrichable = [r for r in results if r.get("exists")]
        total = len(enrichable)

        for i, result in enumerate(enrichable):
            if self._stop:
                break
            self.enrich(result, callback)
            if callback:
                callback(
                    module="Enrichment",
                    message=f"[{i+1}/{total}] Enriching profiles...",
                    progress=int(((i + 1) / total) * 100) if total else 100,
                    results=[],
                )

        return results
