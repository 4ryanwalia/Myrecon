"""
Full username sweep, the website's port of the Android app's engine.

The catalogue (data/platforms_full.json, 560 platforms) is exported from the
app's PlatformCatalogue by CatalogueExportTest, not re-typed, so the two lists
cannot drift by hand. The verdict logic below is a line-by-line port of
UsernameSweep.probe(); the Kotlin carries the long-form reasoning for every
rule, and the comments here only mark where Python had to differ.

Every probe ends on one of three verdicts and never a fourth:

  found      needs positive evidence (API user object, a profile rule, profile
             markup naming the handle, or a page that differs from the
             platform's own no-such-user page)
  not_found  needs negative evidence (404/410, a missing-string, a soft 404,
             or a page identical to a known-impossible handle's)
  unknown    everything else: blocks, challenges, login walls, timeouts, and
             platforms that show one page to everybody

One difference from the app that matters: this runs from a datacentre, and
platforms block datacentre ranges far more than phones. Expect more
"unreachable" here than on-device. Those stay unknown and are counted in the
coverage block, never rewritten into "no account".
"""

import json
import os
import random
import re
import string
import threading
import time
from http.cookiejar import DefaultCookiePolicy
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter

_CATALOGUE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "platforms_full.json"
)

with open(_CATALOGUE_PATH, encoding="utf-8") as _fh:
    CATALOGUE: list = json.load(_fh)

TOTAL = len(CATALOGUE)

# The Extended scan's extra tier: sites from the Maigret list that passed this
# engine's own test (a known-real handle FOUND, two impossible ones not). Built
# by tools/maigret_web_import.py, never hand-edited. Kept apart from CATALOGUE
# so the Pro scan stays the app's 560 and stays fast.
_EXTRA_PATH = os.path.join(os.path.dirname(_CATALOGUE_PATH), "platforms_extra.json")
try:
    with open(_EXTRA_PATH, encoding="utf-8") as _fh:
        EXTRA: list = json.load(_fh)
except FileNotFoundError:
    EXTRA = []

EXTENDED = CATALOGUE + EXTRA
EXTENDED_TOTAL = len(EXTENDED)

FOUND, NOT_FOUND, UNKNOWN = "found", "not_found", "unknown"

# (label, unreachable). Labels match the app's Reason enum word for word.
REASONS = {
    "api_user": ("the platform's API confirmed the account", False),
    "api_absent": ("the platform's API reported no such account", False),
    "exists_string": ("the profile page names this exact handle", False),
    "missing_string": ("the page says there is no such account", False),
    "status_absent": ("the platform returned its not-found status", False),
    "profile_markup": ("the page carries profile markup for this handle", False),
    "differential": ("differs from this platform's no-such-user page", False),
    "not_found_text": ("a soft 404, the page loads and says nobody is here", False),
    "error_title": ("the page title is an error", False),
    "landed_elsewhere": ("the profile URL bounced to a not-found page", False),
    "same_as_control": ("identical to this platform's no-such-user page", False),
    "echo_only": ("this platform shows the same page for any handle", False),
    "ambiguous": ("the platform gave nothing to verify the account with", False),
    "blocked": ("the platform blocked or rate-limited the check", True),
    "challenge": ("a bot check was served instead of an answer", True),
    "server_error": ("the platform's own server failed", True),
    "login_wall": ("a sign-in wall hid the answer", True),
    "transport": ("the request never completed", True),
    "empty_response": ("the platform returned an empty response", True),
    "odd_status": ("the platform answered with an unexpected status", True),
    "invalid_handle": ("this handle cannot form an address on this platform", True),
    "out_of_time": ("the scan ran out of time before this platform answered", True),
}

LANDING_ABSENT = (
    "/404", "/not-found", "/notfound", "/error", "/errors/404", "/oops",
    "/search", "/explore", "/discover",
)
LANDING_WALL = (
    "/login", "/signin", "/sign_in", "/sign-in", "/signup", "/sign_up",
    "/register", "/accounts/login", "/auth", "/session/new", "/checkpoint",
)
CHALLENGE_MARKERS = (
    "js_challenge", "jsc_token",
    "challenge-platform", "cf-browser-verification", "_cf_chl", "cf_chl_opt",
    "just a moment", "checking your browser", "attention required",
    "verifying you are human", "enable javascript and cookies to continue",
    "ddos protection by", "please verify you are a human",
    "px-captcha", "captcha-delivery", "recaptcha/api.js", "hcaptcha.com/1/api.js",
)
AUTH_WALL_MARKERS = (
    "sign in to continue", "log in to continue", "please log in to view",
    "you must be logged in", "login required to view", "members only area",
)
BLOCKED_STATUS = {401, 402, 403, 407, 423, 429, 451, 503, 999}
NOT_FOUND_MARKERS = (
    "page not found", "user not found", "profile not found", "page doesn't exist",
    "couldn't find this account", "couldn't find that page", "doesn't exist",
    "does not exist", "no such user", "sorry, this page", "page isn't available",
    "page not available", "account suspended", "user does not exist",
    "this account doesn't exist", "nothing to see here",
    "profile unavailable", "this profile is unavailable", "account deleted",
    "account not found", "no user found", "user unavailable",
    "we couldn't find", "we could not find", "nothing was found",
    "no results found", "this page is gone", "user has been deleted",
)
TITLE_ERROR_MARKERS = (
    "not found", "error", "404", "page unavailable", "oops", "doesn't exist",
    "does not exist", "nothing here",
)
PROFILE_MARKUP = (
    "og:type\" content=\"profile", "og:type' content='profile",
    "\"@type\":\"person\"", "\"@type\": \"person\"",
    "\"@type\":\"profilepage\"", "\"@type\": \"profilepage\"",
    "itemtype=\"http://schema.org/person\"",
    "itemtype=\"https://schema.org/person\"",
)
PLACEHOLDER_MARKERS = (
    "default", "placeholder", "anonymous", "no-avatar", "noavatar",
    "blank", "generic", "mystery", "gravatar.com/avatar/00000",
    "ogimage", "og-image", "og_image", "opengraph",
    "/share/", "twitter-card", "social-card", "default-avatar",
    "/letter/",
    "no_portrait", "no-portrait", "noportrait",
    "missing_user", "missing-user", "missinguser",
    "avatar_placeholder", "user-placeholder", "empty-avatar",
)
LOGO_FILES = ("logo.png", "logo.jpg", "logo.jpeg", "logo.svg", "logo.webp")
OG_ARTWORK_FILES = ("og.png", "og.jpg", "og.jpeg", "og.webp")
AVATAR_FIELDS = (
    "profile_pic_url_hd", "profile_pic_url", "avatar_template", "avatar_url",
    "icon_img", "image_url", "image_xlarge_url", "image_large_url",
    "profile_image_url_https", "profile_image_url", "avatar_static", "avatar",
    "avatarUrl", "photo_url", "picture", "90x90", "thumbnail_url", "image",
)
PINTEREST_PROFILE_FIELDS = (
    '"full_name"', '"image_xlarge_url"', '"image_large_url"',
    '"follower_count"', '"following_count"',
)
INSTAGRAM_PROFILE_FIELDS = (
    '"edge_followed_by"', '"edge_follow"', '"biography"',
    '"profile_pic_url_hd"', '"edge_owner_to_timeline_media"',
    '"is_private"', '"full_name"',
)

UA = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

BODY_PEEK_BYTES = 48_000
PEEK_LIMITS = {
    "Pinterest": 1_800_000,
    "YouTube": 1_000_000,
    # Floor and ceiling both matter; see INSTAGRAM_PEEK_BYTES in the Kotlin.
    # Past ~300 KB Instagram echoes any handle and every search would "find" it.
    "Instagram": 160_000,
}

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL)
PROFILE_USERNAME_RE = re.compile(
    r"""<meta[^>]+property=["']profile:username["'][^>]+content=["']([^"']+)["']""", re.I
)
OG_IMAGE_RES = (
    re.compile(r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']""", re.I),
    re.compile(r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']""", re.I),
    re.compile(r"""<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)["']""", re.I),
    re.compile(r"""<meta[^>]+content=["']([^"']+)["'][^>]+name=["']twitter:image["']""", re.I),
)
OG_TITLE_RE = re.compile(r"""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']""", re.I)
UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")
_WS = re.compile(r"\s+")

# A handle substituted into a hostname ({username}.tumblr.com) must be one DNS
# label. The username validator allows "." and "@", and "@" in the authority
# is userinfo, so without this a handle could move where the request goes.
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)

CONNECT_TIMEOUT = 6
READ_TIMEOUT = 8
CONCURRENCY = 24
# Past this the remaining platforms are reported "out of time", unknown and
# counted as unreachable, instead of holding the stream open indefinitely.
DEADLINE_SECONDS = 90


def _host_templated(template: str) -> bool:
    return re.match(r"https?://[^/]*\{username\}", template) is not None


def _read_peek(resp: requests.Response, limit: int) -> str:
    """Up to `limit` decoded bytes of the body, as text."""
    chunks, got = [], 0
    try:
        for chunk in resp.iter_content(chunk_size=16384, decode_unicode=False):
            if not chunk:
                continue
            chunks.append(chunk)
            got += len(chunk)
            if got >= limit:
                break
    except Exception:  # noqa: BLE001 - a truncated read is still a read
        pass
    raw = b"".join(chunks)[:limit]
    return raw.decode(resp.encoding or "utf-8", errors="replace")


def clean_avatar(raw, base=None):
    """Normalise an avatar URL or reject it. Port of cleanAvatar()."""
    if not raw:
        return None
    url = raw.strip()
    url = UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), url)
    url = url.replace("&amp;", "&").replace("\\/", "/").replace("{size}", "120")
    if not url.lower().startswith("http"):
        if not base:
            return None
        url = urljoin(base, url)
        if not url.lower().startswith("http"):
            return None
    lower = url.lower()
    if any(m in lower for m in PLACEHOLDER_MARKERS):
        return None
    for f in OG_ARTWORK_FILES + LOGO_FILES:
        if lower.endswith("/" + f) or lower.endswith("-" + f) or lower.endswith("_" + f):
            return None
    first = url.find("?")
    second = url.find("?", first + 1) if first >= 0 else -1
    return url[:second] if second > 0 else url


def _avatar_from(peek, base):
    for rx in OG_IMAGE_RES:
        m = rx.search(peek)
        cleaned = clean_avatar(m.group(1), base) if m else None
        if cleaned:
            return cleaned
    return None


def _json_field(body, field):
    m = re.search(r'"%s"\s*:\s*"([^"]+)"' % re.escape(field), body)
    if not m:
        return None
    value = m.group(1).replace("\\/", "/")
    return value if value.strip() else None


def _avatar_from_json(body, base):
    for f in AVATAR_FIELDS:
        cleaned = clean_avatar(_json_field(body, f), base)
        if cleaned:
            return cleaned
    return None


def _profile_object_in(body, handle, fields):
    escaped = re.escape(handle.lower())
    has_handle = re.search(r"""["']username["']\s*:\s*["']%s["']""" % escaped, body) is not None
    return has_handle and any(f in body for f in fields)


def _title_names_handle(peek, title, handle):
    m = OG_TITLE_RE.search(peek)
    og_title = m.group(1) if m else ""
    at = r"(?:@|&#0*64;|&commat;|%40)"
    rx = re.compile(r"\(\s*" + at + re.escape(handle) + r"\s*\)")
    return bool(rx.search(title) or rx.search(og_title))


def _display_name_in(raw, name):
    m = OG_TITLE_RE.search(raw)
    if not m:
        return None
    value = m.group(1).strip()
    return value if value and value.lower() != name.lower() else None


def _control_handle():
    # Twelve lowercase letters, never digits: see controlHandle() in the Kotlin.
    return "".join(random.choice(string.ascii_lowercase) for _ in range(12))


def _path(url):
    try:
        return urlsplit(url).path.lower()
    except ValueError:
        return None


class _Shape:
    __slots__ = ("status", "title", "length", "looks_absent")

    def __init__(self, status, title, length, looks_absent):
        self.status, self.title, self.length, self.looks_absent = status, title, length, looks_absent


def _shape_of(p, status, body, handle):
    lower = body.lower()
    h = handle.lower()
    m = TITLE_RE.search(lower)
    title = _WS.sub(" ", (m.group(1) if m else "").replace(h, "")).strip()
    return _Shape(
        status=status,
        title=title,
        length=len(lower.replace(h, "")),
        looks_absent=(status == p["missing_status"] or status == 410
                      or any(x in lower for x in NOT_FOUND_MARKERS)
                      or any(x in title for x in TITLE_ERROR_MARKERS)),
    )


def _differs(a, b):
    if a.status != b.status or a.title != b.title:
        return True
    hi, lo = max(a.length, b.length), min(a.length, b.length)
    return hi > 0 and lo / hi < 0.8


class Sweep:
    """One sweep: a pooled session, one control handle, a shared deadline."""

    def __init__(self, handle, deadline_seconds=DEADLINE_SECONDS, concurrency=CONCURRENCY):
        self.handle = handle.strip().lstrip("@")
        self.concurrency = concurrency
        self.control = _control_handle()
        self.deadline = time.monotonic() + deadline_seconds
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=concurrency, max_retries=0)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        # No cookie jar, like the app's OkHttp client. With one, the first
        # request to a site sets cookies the control probe then carries, and
        # the two responses being compared are no longer the same kind of
        # visit.
        self.session.cookies.set_policy(DefaultCookiePolicy(allowed_domains=[]))
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    # ── requests ─────────────────────────────────────────────────

    def _html_get(self, p, url):
        headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            **(p.get("html_headers") or {}),
        }
        return self.session.get(url, headers=headers, stream=True,
                                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), allow_redirects=True)

    def _url_for(self, p, handle, key="url"):
        return p[key].replace("{username}", handle)

    # ── verdict helpers ──────────────────────────────────────────

    def _hit(self, p, verdict, url, status, confidence, reason, avatar=None, name=None):
        label, unreachable = REASONS[reason]
        return {
            "platform": p["name"],
            "platform_category": p["category"],
            "url": url,
            "verdict": verdict,
            "exists": verdict == FOUND,
            "status_code": status,
            "confidence": confidence,
            "reason_code": reason,
            "reason": label,
            "unreachable": unreachable if verdict == UNKNOWN else False,
            "profile_pic_url": avatar,
            "display_name": name,
            "source": "username_sweep",
            "username": self.handle,
        }

    def _probe_api(self, p, handle):
        api = p.get("api")
        if not api:
            return None
        api = api.replace("{username}", handle)
        headers = {"User-Agent": UA, "Accept": "application/json", **(p.get("api_headers") or {})}
        try:
            resp = self.session.get(api, headers=headers, stream=True,
                                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            with resp:
                code = resp.status_code
                limit = 128_000 if p["name"] == "Instagram" else 64_000
                body = _read_peek(resp, limit)
        except Exception:  # noqa: BLE001 - fall back to the HTML check
            return None
        lower = body.strip().lower()
        url = self._url_for(p, handle)

        missing = (p.get("api_missing") or "").lower()
        if missing and missing in lower:
            return self._hit(p, NOT_FOUND, url, code, "none", "api_absent")
        if code == 200:
            empty = lower in ("", "[]", "{}", "null") or '"user": null' in lower or '"user":null' in lower
            required = (p.get("api_exists") or "").lower()
            if empty:
                return self._hit(p, NOT_FOUND, url, code, "none", "api_absent")
            if required and required not in lower:
                return None
            return self._hit(
                p, FOUND, url, code, "high", "api_user",
                avatar=_avatar_from_json(body, api),
                name=_json_field(body, "full_name") or _json_field(body, "name"),
            )
        if code in (p["missing_status"], 404, 410):
            return self._hit(p, NOT_FOUND, url, code, "none", "api_absent")
        return None

    def _page_avatar(self, p, handle):
        url = self._url_for(p, handle)
        try:
            resp = self._html_get(p, url)
            with resp:
                if resp.status_code != p["ok_status"]:
                    return None
                raw = _read_peek(resp, PEEK_LIMITS.get(p["name"], BODY_PEEK_BYTES))
        except Exception:  # noqa: BLE001 - strictly additive
            return None
        return _avatar_from(raw, url) or _avatar_from_json(raw, url)

    def _control_shape(self, p):
        try:
            resp = self._html_get(p, self._url_for(p, self.control))
            with resp:
                body = _read_peek(resp, PEEK_LIMITS.get(p["name"], BODY_PEEK_BYTES))
                code = resp.status_code
        except Exception:  # noqa: BLE001
            return None
        if not body.strip() or any(m in body.lower() for m in CHALLENGE_MARKERS):
            return None
        return _shape_of(p, code, body, self.control)

    # ── the probe ────────────────────────────────────────────────

    def probe(self, p):  # noqa: C901 - mirrors the Kotlin one branch at a time
        handle = self.handle
        url = self._url_for(p, handle)

        if _host_templated(p["url"]) and not _DNS_LABEL.match(handle):
            return self._hit(p, UNKNOWN, url, 0, "unverified", "invalid_handle")
        # Imported platforms carry the site's own username rule. A handle the
        # site could never register would 404, and 404 reads as proof of
        # absence, so it is unknown instead of a confident "no account".
        rule = p.get("regex_check")
        if rule:
            try:
                if not re.search(rule, handle):
                    return self._hit(p, UNKNOWN, url, 0, "unverified", "invalid_handle")
            except re.error:
                pass
        if time.monotonic() > self.deadline or self._stop.is_set():
            return self._hit(p, UNKNOWN, url, 0, "unverified", "out_of_time")

        api = self._probe_api(p, handle)
        if api is not None:
            if api["verdict"] == FOUND and not api.get("profile_pic_url"):
                api["profile_pic_url"] = self._page_avatar(p, handle)
            return api

        unknown = lambda r, c: self._hit(p, UNKNOWN, url, c, "unverified", r)  # noqa: E731
        absent = lambda r, c: self._hit(p, NOT_FOUND, url, c, "none", r)  # noqa: E731

        try:
            resp = self._html_get(p, url)
            with resp:
                code = resp.status_code
                landed = _path(resp.url) or ""
                raw = _read_peek(resp, PEEK_LIMITS.get(p["name"], BODY_PEEK_BYTES)) \
                    if code == p["ok_status"] else ""
        except Exception:  # noqa: BLE001 - timeouts, DNS and TLS are unknown
            return unknown("transport", 0)

        if code in BLOCKED_STATUS:
            return unknown("blocked", code)
        if code >= 500:
            return unknown("server_error", code)
        if code == p["missing_status"] or code == 410:
            return absent("status_absent", code)
        if code != p["ok_status"]:
            return unknown("odd_status", code)
        if not raw.strip():
            return unknown("empty_response", code)

        peek = raw.lower()
        h = handle.lower()
        m = TITLE_RE.search(peek)
        title = m.group(1).strip() if m else ""

        if any(x in peek for x in CHALLENGE_MARKERS):
            return unknown("challenge", code)
        if any(landed.endswith(x) or landed == x for x in LANDING_WALL):
            return unknown("login_wall", code)
        if any(landed.endswith(x) or landed == x for x in LANDING_ABSENT):
            return absent("landed_elsewhere", code)
        asked = _path(url)
        if landed in ("/", "") and asked not in (None, "", "/"):
            return absent("landed_elsewhere", code)

        missing = (p.get("missing") or "").replace("{username}", handle).lower()
        if missing and missing in peek:
            return absent("missing_string", code)
        exists = (p.get("exists") or "").replace("{username}", handle).lower()
        if exists and exists in peek:
            return self._hit(p, FOUND, url, code, "high", "exists_string",
                             avatar=_avatar_from(raw, url) or _avatar_from_json(raw, url),
                             name=_display_name_in(raw, p["name"]))

        if any(x in peek for x in NOT_FOUND_MARKERS):
            return absent("not_found_text", code)
        if any(x in title for x in TITLE_ERROR_MARKERS):
            return absent("error_title", code)
        if any(x in peek for x in AUTH_WALL_MARKERS):
            return unknown("login_wall", code)

        def hit(conf, reason):
            return self._hit(p, FOUND, url, code, conf, reason,
                             avatar=_avatar_from(raw, url) or _avatar_from_json(raw, url),
                             name=_display_name_in(raw, p["name"]))

        if p.get("echoes_handle"):
            return unknown("echo_only", code)
        if _title_names_handle(peek, title, h):
            return hit("high", "profile_markup")

        dm = PROFILE_USERNAME_RE.search(raw)
        if dm and dm.group(1).strip().lower() == h:
            return hit("high", "profile_markup")
        profile_markup = any(x in peek for x in PROFILE_MARKUP)
        mentions_handle = h in peek
        if profile_markup and mentions_handle:
            return hit("high", "profile_markup")

        embedded = {"Pinterest": PINTEREST_PROFILE_FIELDS,
                    "Instagram": INSTAGRAM_PROFILE_FIELDS}.get(p["name"])
        if embedded and _profile_object_in(peek, handle, embedded):
            return hit("high", "profile_markup")

        target = _shape_of(p, code, raw, handle)
        reference = self._control_shape(p)
        if reference is None:
            return unknown("ambiguous", code)
        if not _differs(target, reference):
            return absent("same_as_control", code) if reference.looks_absent \
                else unknown("echo_only", code)
        if reference.looks_absent:
            return hit("medium", "differential")
        if profile_markup:
            return hit("medium", "differential")
        return unknown("ambiguous", code)

    # ── the sweep ────────────────────────────────────────────────

    def run(self, on_result=None, platforms=None):
        """
        Probe every platform; call `on_result(hit, checked, total)` as each
        lands. Returns (hits, coverage).
        """
        platforms = platforms if platforms is not None else CATALOGUE
        total = len(platforms)
        hits = []
        checked = 0
        lock = threading.Lock()

        def guarded(p):
            try:
                return self.probe(p)
            except Exception:  # noqa: BLE001 - one platform never fails a sweep
                return self._hit(p, UNKNOWN, self._url_for(p, self.handle), 0,
                                 "unverified", "transport")

        try:
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                futures = [pool.submit(guarded, p) for p in platforms]
                for fut in as_completed(futures):
                    hit = fut.result()
                    with lock:
                        hits.append(hit)
                        checked += 1
                        n = checked
                    if on_result:
                        on_result(hit, n, total)
        finally:
            self.session.close()

        coverage = {
            "total": total,
            "found": sum(1 for h in hits if h["verdict"] == FOUND),
            "not_found": sum(1 for h in hits if h["verdict"] == NOT_FOUND),
            "undetermined": sum(1 for h in hits if h["verdict"] == UNKNOWN and not h["unreachable"]),
            "unreachable": sum(1 for h in hits if h["verdict"] == UNKNOWN and h["unreachable"]),
        }
        return hits, coverage
