"""Exact public profile identities for sites with an authoritative HTML object.

These checks never infer ownership, trust an echoed URL alone, or fall back to
a different no-user page when the account object is missing or malformed.
"""
from html.parser import HTMLParser
import json
import re
from urllib.parse import unquote, urlsplit


class _ProfilePage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.in_title = False
        self.app_script = False
        self.script = []
        self.apps = []
        self.frames = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "script" and attrs.get("data-page") == "app" and attrs.get("type") == "application/json":
            self.app_script = True
            self.script = []
        elif tag == "turbo-frame":
            self.frames.append(attrs)

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.app_script:
            self.script.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.app_script:
            try:
                self.apps.append(json.loads("".join(self.script)))
            except ValueError:
                pass
            self.app_script = False


def profile_identity(platform, raw, final_url, handle):
    """True only for an exact, active account object on its own profile path."""
    parsed_url = urlsplit(final_url)
    path = unquote(parsed_url.path).rstrip("/")
    host = (parsed_url.hostname or "").removeprefix("www.")
    expected_host, expected_path = {
        "Buymeacoffee": ("buymeacoffee.com", f"/{handle}"),
        "OpenStreetMap": ("openstreetmap.org", f"/user/{handle}"),
    }[platform]
    if parsed_url.scheme != "https" or host != expected_host or path.casefold() != expected_path.casefold():
        return False
    page = _ProfilePage()
    try:
        page.feed(raw)
    except (ValueError, TypeError):
        return False
    if platform == "OpenStreetMap":
        exact_title = "".join(page.title).strip().casefold() == f"{handle} | OpenStreetMap".casefold()
        return exact_title and any(re.fullmatch(r"user_[1-9]\d*_heatmap", frame.get("id", ""))
            and unquote(frame.get("src", "")).casefold() == f"/user/{handle}/heatmap".casefold()
            for frame in page.frames)
    for app in page.apps:
        if not isinstance(app, dict) or app.get("component") != "Home/HomeLayout":
            continue
        props = app.get("props")
        creator = props.get("creator_data") if isinstance(props, dict) else None
        data = creator.get("data") if isinstance(creator, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("slug"), str):
            continue
        ids = [data.get("user_id"), data.get("project_id")]
        if (data["slug"].casefold() == handle.casefold()
                and all(type(value) is int and value > 0 for value in ids)
                and type(data.get("active")) is int and data["active"] == 1
                and data.get("deleted") is False):
            return True
    return False


def reddit_identity(body, handle):
    """Require Reddit's typed account object, not a nested name in arbitrary JSON."""
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return False
    if not isinstance(payload, dict) or payload.get("kind") != "t2":
        return False
    account = payload.get("data")
    return (isinstance(account, dict) and isinstance(account.get("name"), str)
        and account["name"].casefold() == handle.casefold()
        and isinstance(account.get("id"), str) and bool(re.fullmatch(r"[a-z0-9]+", account["id"])))
