"""Reviewed public account adapters. No generic status/echo/differential fallback.

Evidence paths adapted from user-scanner (MIT); see docs/username-integrations.md
and third-party/user-scanner-LICENSE. Every adapter makes one bounded request.
"""
import html
import json
import math
import re
import time
from html.parser import HTMLParser
from urllib.parse import quote, urlencode, urlsplit


_SPECS = (
    ("daily.dev", "Developer", "https://daily.dev/{username}", None, "dev/daily_dev.py"),
    ("Modrinth", "Gaming", "https://modrinth.com/user/{username}", "https://api.modrinth.com/v2/user/{username}", "gaming/modrinth.py"),
    ("stats.fm", "Music", "https://stats.fm/{username}", "https://api.stats.fm/api/v1/users/{username}", "music/statsfm.py"),
    ("Inkitt", "Creative", "https://www.inkitt.com/{username}", None, "creator/inkitt.py"),
    ("Payhip", "Creative", "https://payhip.com/{username}", None, "creator/payhip.py"),
    ("Luma", "Social", "https://luma.com/user/{username}", None, "creator/luma.py"),
    ("Bio Site", "Creative", "https://bio.site/{username}", None, "creator/bio_site.py"),
    ("Warpcast", "Social", "https://warpcast.com/{username}", "https://client.warpcast.com/v2/user-by-username?username={username}", "social/warpcast.py"),
    ("Character.AI", "Social", "https://character.ai/profile/{username}", None, "social/characterai.py"),
)

PLATFORMS = [dict(name=name, category=category, url=url, integration=name,
                  reference_module=reference, endpoint=endpoint, ok_status=200,
                  missing_status=404, regex_check=r"^[A-Za-z0-9_.-]{1,64}$")
             for name, category, url, endpoint, reference in _SPECS]
next(p for p in PLATFORMS if p["name"] == "Warpcast")["regex_check"] = r"^[0-9a-z][0-9a-z-]{0,15}(?:\.eth|\.base\.eth)?$"


def append_missing(base, extras):
    """Compare account hosts (including API hosts), never reference filenames.

    These nine services have one account namespace per host. A future catalogue
    entry on either host suppresses the adapter instead of adding another probe.
    Existing forum subdomains remain distinct account namespaces.
    """
    def host(url):
        return (urlsplit(url or "").hostname or "").removeprefix("www.")
    covered = {host(p.get(key)) for p in base + extras for key in ("url", "api", "endpoint")}
    additions = []
    for p in PLATFORMS:
        hosts = {host(p["url"]), host(p.get("endpoint"))} - {""}
        if not hosts.intersection(covered):
            additions.append(p)
            covered.update(hosts)
    return base + additions


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []
        self.next_data = None

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.active, self.parts = True, []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.next_data = json.loads("".join(self.parts))
            self.active = False


def _assigned(body, marker):
    match = re.search(marker, body)
    if not match:
        return None
    return json.JSONDecoder().raw_decode(body[match.end():].lstrip())[0]


def _obj(value):
    return value if isinstance(value, dict) else {}


def _same(value, handle):
    return isinstance(value, str) and value.casefold() == handle.casefold()


def _identity(value):
    return (isinstance(value, str) and bool(value.strip())) or (type(value) is int and value > 0)


def _text(value, limit=2000):
    return html.unescape(re.sub(r"<[^>]+>", " ", value)).strip()[:limit] if isinstance(value, str) else None


def _link(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    parts = urlsplit(value)
    return value if parts.scheme in ("https", "http") and parts.hostname and not parts.username and not parts.password else None


def _details(account, name=None, bio=None, avatar=None, links=(), stats=None):
    out = {}
    for field, value in (("display_name", _text(name, 200)), ("bio", _text(bio)),
                         ("profile_pic_url", _link(avatar))):
        if value:
            out[field] = value
    public_links = list(dict.fromkeys(v for v in map(_link, links) if v))[:30]
    if public_links:
        out["public_links"] = public_links
    statistics = {k: v for k, v in (stats or {}).items() if type(v) in (int, float) and math.isfinite(v) and v >= 0}
    if statistics:
        out["statistics"] = statistics
        for field in ("followers", "following"):
            if field in statistics:
                out[field] = statistics[field]
    return out


def parse_account(name, code, body, handle):
    """Return (verdict, metadata); unrecognized/partial objects are unknown."""
    if name in ("Modrinth", "stats.fm", "Warpcast") and code == 404:
        return "not_found", {}
    if name in ("daily.dev", "Bio Site") and code == 404:
        return "not_found", {}
    if name == "Character.AI":
        data = _obj(json.loads(body))
        error = _obj(_obj(_obj(data.get("error")).get("json")).get("data"))
        if code == 500 and error.get("path") == "social.publicProfile" and _obj(error.get("axiosErrorData")).get("upstreamStatus") == 404:
            return "not_found", {}
        a = _obj(_obj(_obj(data.get("result")).get("data")).get("json"))
        if code == 200 and _same(a.get("username"), handle):
            chars = a.get("characters")
            stats = {"followers": a.get("num_followers"), "following": a.get("num_following")}
            if isinstance(chars, list):
                stats["characters"] = len(chars)
                for field, source in (("interactions", "participant__num_interactions"), ("upvotes", "upvotes")):
                    counts = [c.get(source) for c in chars if isinstance(c, dict)]
                    if len(counts) == len(chars) and all(type(v) is int and v >= 0 for v in counts):
                        stats[field] = sum(counts)
            avatar = a.get("avatar_file_name")
            return "found", _details(a, a.get("name"), a.get("bio"),
                f"https://characterai.io/i/200/static/avatars/{quote(avatar, safe='')}?anim=0" if isinstance(avatar, str) else None, stats=stats)
    elif name in ("Modrinth", "stats.fm", "Warpcast"):
        data = _obj(json.loads(body))
        a = data if name == "Modrinth" else _obj(data.get("item")) if name == "stats.fm" else _obj(_obj(data.get("result")).get("user"))
        # stats.fm resolves both account IDs and custom handles; neither a bare
        # success flag nor a different account is evidence for the queried one.
        matches = _same(a.get("username"), handle) if name != "stats.fm" else any(_same(a.get(k), handle) for k in ("id", "customId", "username"))
        identity = a.get("fid") if name == "Warpcast" else a.get("id")
        if code == 200 and _identity(identity) and matches:
            profile = _obj(a.get("profile"))
            return "found", _details(a, a.get("name") or a.get("displayName"),
                a.get("bio") or _obj(profile.get("bio")).get("text"),
                a.get("avatar_url") or a.get("image") or _obj(a.get("pfp")).get("url"),
                stats={"followers": a.get("followerCount"), "following": a.get("followingCount")})
    elif name in ("daily.dev", "Luma"):
        scripts = _Scripts()
        scripts.feed(body)
        data = _obj(scripts.next_data)
        props = _obj(_obj(data.get("props")).get("pageProps"))
        initial = _obj(props.get("initialData"))
        a = _obj(props.get("user")) if name == "daily.dev" else _obj(initial.get("user"))
        if name == "Luma" and data.get("page") == "/user/[...username]" and props.get("status") == 404 and props.get("initialData") is None:
            return "not_found", {}
        identity = a.get("id") if name == "daily.dev" else a.get("api_id")
        if code == 200 and _identity(identity) and _same(a.get("username"), handle) and (name != "Luma" or data.get("page") == "/user/[...username]"):
            stats = _obj(props.get("userStats"))
            links = [a.get("website")]
            if name == "Luma":
                for field, template in (("instagram_handle", "https://www.instagram.com/{}/"),
                                        ("linkedin_handle", "https://www.linkedin.com/in/{}"),
                                        ("tiktok_handle", "https://www.tiktok.com/@{}"),
                                        ("twitter_handle", "https://x.com/{}"),
                                        ("youtube_handle", "https://www.youtube.com/@{}")):
                    value = a.get(field)
                    if isinstance(value, str) and value:
                        links.append(template.format(quote(value.lstrip("@"), safe="")))
            return "found", _details(a, a.get("name"), a.get("bio") or a.get("bio_short"), a.get("image") or a.get("avatar_url"),
                links, {"followers": stats.get("numFollowers"), "following": stats.get("numFollowing"),
                "reputation": a.get("reputation"), "events_hosted": initial.get("event_hosted_count"), "events_attended": initial.get("event_attended_count")})
    elif name == "Inkitt":
        a = _assigned(body, r"globalData\.user\s*=\s*")
        if code == 404 and a == {} and 'controller: "errors"' in body and 'action: "not_found"' in body:
            return "not_found", {}
        a = _obj(a)
        if code == 200 and _identity(a.get("id")) and _same(a.get("username"), handle):
            return "found", _details(a, a.get("name"), a.get("description") or a.get("about"), a.get("large_profile_picture_url"),
                [a.get(k) for k in ("homepage_url", "donate_url", "facebook_url", "twitter_url", "instagram_url")],
                {"followers": a.get("followers_count"), "following": a.get("followings_count"), "stories": a.get("published_stories_count"), "wall_posts": a.get("wall_posts_count")})
    elif name == "Payhip":
        if code == 404 and "<title>404 Page Not Found</title>" in body and "The page you requested was not found." in body:
            return "not_found", {}
        a = _obj(_obj(_assigned(body, r"window\.payhipShop\s*=\s*")).get("user"))
        if code == 200 and _same(a.get("username"), handle):
            logo = _obj(_obj(_obj(a.get("resizedLogo")).get("original")))
            bio = a.get("bio")
            links = [a.get("websiteUrl")] + list(_obj(a.get("socialMedia")).values())
            if isinstance(bio, str):
                links += re.findall(r'href=["\']([^"\']+)', html.unescape(bio))
            return "found", _details(a, a.get("shopName"), bio, logo.get("src"), links)
    elif name == "Bio Site":
        a = _obj(_assigned(body, r"window\.initial_state\s*=\s*"))
        if code == 200 and _same(_obj(a.get("metadata")).get("handle"), handle):
            header = _obj(a.get("header"))
            if header:
                return "found", _details(header, header.get("name"), header.get("bio"), header.get("profilePhoto") or header.get("profile_photo"))
    return "unknown", {}


def probe(sweep, platform):
    """Use the sweep's timeout/deadline/session and emit its normal result shape."""
    from modules.sweep import AUTH_WALL_MARKERS, CHALLENGE_MARKERS, BLOCKED_STATUS, UA
    handle = sweep.handle
    encoded = quote(handle, safe="")
    profile_url = platform["url"].replace("{username}", encoded)
    endpoint = endpoint_url(platform, handle)
    def hit(verdict, code, reason, details=None):
        result = sweep._hit(platform, verdict, profile_url, code, "high" if verdict == "found" else "none" if verdict == "not_found" else "unverified", reason)
        if verdict == "found":
            result.update(details or {})
            result["metadata_source"] = {"platform": platform["name"], "url": endpoint, "basis": "public account object"}
            result["metadata_complete"] = True
        return result
    try:
        # Do not follow redirects into login walls, landing pages or another
        # account. No HTML retry or control request after an ambiguous answer.
        with sweep.session.get(endpoint, headers={"User-Agent": UA, "Accept": "application/json,text/html"},
                               timeout=(6, 8), stream=True, allow_redirects=False) as response:
            code = response.status_code
            chunks, size = [], 0
            read_deadline = min(sweep.deadline, time.monotonic() + 8)
            for chunk in response.iter_content(chunk_size=16384):
                size += len(chunk)
                if size > 1_000_000 or time.monotonic() > read_deadline:
                    return hit("unknown", code, "transport")
                chunks.append(chunk)
            body = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        lower = body.lower()
        if code in BLOCKED_STATUS:
            return hit("unknown", code, "blocked")
        if 300 <= code < 400:
            return hit("unknown", code, "ambiguous")
        if any(marker in lower for marker in CHALLENGE_MARKERS):
            return hit("unknown", code, "challenge")
        if any(marker in lower for marker in AUTH_WALL_MARKERS):
            return hit("unknown", code, "login_wall")
        verdict, details = parse_account(platform["name"], code, body, handle)
        api = platform["name"] in ("Modrinth", "stats.fm", "Warpcast", "Character.AI")
        if verdict == "found":
            reason = "api_user" if api else "profile_markup"
        elif verdict == "not_found":
            reason = "api_absent" if api else "status_absent" if code == 404 else "missing_string"
        else:
            reason = "server_error" if code >= 500 else "ambiguous"
        return hit(verdict, code, reason, details)
    except (ValueError, TypeError, AttributeError):
        return hit("unknown", locals().get("code", 0), "ambiguous")
    except Exception:
        return hit("unknown", 0, "transport")


def endpoint_url(platform, handle):
    """The exact, secret-free attribution URL shared with worker normalization."""
    if platform["name"] == "Character.AI":
        return "https://character.ai/api/trpc/social.publicProfile?" + urlencode({"input": json.dumps({"json": {"username": handle}})})
    return (platform.get("endpoint") or platform["url"]).replace("{username}", quote(handle, safe=""))
