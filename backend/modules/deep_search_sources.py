"""Bounded public API adapters for the app's six activity sources and registries.

Only fixed provider endpoints are fetched. Owner links are reported, never crawled.
An unavailable activity feed does not erase a confirmed profile.
"""
import datetime as dt
import html
import re
import time
from urllib.parse import quote, urlsplit

from core.netguard import safe_get
from modules.deep_search_plan import safe_url


class Unavailable(Exception):
    pass


class Missing(Exception):
    pass


class PublicClient:
    def __init__(self, seconds=14):
        self.deadline = time.monotonic() + seconds

    def get(self, url, params=None, accept="application/json", text=False):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise Unavailable()
        try:
            with safe_get(url, params=params, headers={"User-Agent": "MyRecon/1.1 (+https://www.myrecon.xyz)",
                           "Accept": accept}, timeout=(min(3, left), min(5, left)), stream=True) as response:
                if response.status_code == 404:
                    raise Missing()
                if response.status_code != 200:
                    raise Unavailable()
                chunks, size = [], 0
                for chunk in response.iter_content(16384):
                    size += len(chunk)
                    if size > 2_000_000 or time.monotonic() > self.deadline:
                        raise Unavailable()
                    chunks.append(chunk)
                if text:
                    return b"".join(chunks).decode("utf-8", errors="replace")
                import json
                return json.loads(b"".join(chunks))
        except Missing:
            raise
        except Exception:
            raise Unavailable() from None

    def optional(self, url, params=None):
        try:
            return self.get(url, params), True
        except (Missing, Unavailable):
            return None, False


def plain(value, limit=400):
    text = html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))
    return " ".join(text.split())[:limit]


def day(value):
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, dt.timezone.utc).date().isoformat()
    return str(value or "")[:10] or None


def link(raw, label=None, verified=False):
    raw = str(raw or "").strip()
    if raw and not re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.I):
        raw = "https://" + raw
    url = safe_url(raw)
    if not url:
        return None
    host = urlsplit(url).hostname.removeprefix("www.")
    return {"label": label or host, "url": url, "verified": verified}


def declared(*links):
    result, seen = [], set()
    for item in links:
        if item and item["url"].rstrip("/").lower() not in seen:
            seen.add(item["url"].rstrip("/").lower())
            result.append(item)
    return result


def bio_links(text):
    return [link(url) for url in re.findall(r"https?://[^\s\"'<>\)\]]+", str(text or ""))]


def post(text, url, context=None, date=None):
    url = safe_url(url)
    return {"text": plain(text), "url": url, "context": plain(context), "date": day(date)} if text and url else None


def presence(platform, handle, url, source, **extra):
    return {"platform": platform, "handle": handle, "url": url, "source": source,
            "posts": [], "declared": [], "stats": {}, **extra}


def same_handle(actual, expected):
    if not isinstance(actual, str) or actual.casefold() != expected.casefold():
        raise Unavailable()


def github(h):
    c = PublicClient()
    u = c.get("https://api.github.com/users/" + quote(h, safe=""))
    same_handle(u.get("login"), h)
    events, available = c.optional("https://api.github.com/users/" + quote(h, safe="") + "/events/public", {"per_page": 30})
    posts = []
    for ev in events if isinstance(events, list) else []:
        payload = ev.get("payload") or {}
        comment = payload.get("comment") or payload.get("review") or {}
        p = post(comment.get("body"), comment.get("html_url"), (ev.get("repo") or {}).get("name"), ev.get("created_at"))
        if p:
            posts.append(p)
    return presence("GitHub", u["login"], "https://github.com/" + quote(u["login"]), "GitHub public API",
                    display_name=u.get("name"), bio=plain(" · ".join(str(u[k]) for k in ("bio", "company", "location") if u.get(k))),
                    since=day(u.get("created_at")), stats={"Repos": u.get("public_repos"), "Followers": u.get("followers")},
                    declared=declared(link(u.get("blog")), link("https://x.com/" + quote(u["twitter_username"], safe=""), "X") if u.get("twitter_username") else None, *bio_links(u.get("bio"))),
                    posts=posts[:5], activity_available=available)


def hacker_news(h):
    c = PublicClient()
    u = c.get("https://hacker-news.firebaseio.com/v0/user/" + quote(h, safe="") + ".json")
    if u is None:
        raise Missing()
    same_handle(u.get("id"), h)
    comments, available = c.optional("https://hn.algolia.com/api/v1/search_by_date", {"tags": "comment,author_" + h, "hitsPerPage": 5})
    posts = [post(x.get("comment_text"), "https://news.ycombinator.com/item?id=" + quote(str(x.get("objectID", ""))),
                  x.get("story_title"), x.get("created_at")) for x in (comments or {}).get("hits", []) if x.get("author") == h]
    return presence("Hacker News", h, "https://news.ycombinator.com/user?id=" + quote(h), "Hacker News Firebase / Algolia",
                    bio=plain(u.get("about")), since=day(u.get("created")), stats={"Karma": u.get("karma")},
                    declared=declared(*bio_links(html.unescape(u.get("about") or ""))), posts=[p for p in posts if p], activity_available=available)


def reddit(h):
    c = PublicClient()
    result = c.get("https://www.reddit.com/user/" + quote(h, safe="") + "/about.json")
    u = result.get("data") or {}
    if result.get("kind") != "t2":
        raise Unavailable()
    same_handle(u.get("name"), h)
    comments, available = c.optional("https://www.reddit.com/user/" + quote(h, safe="") + "/comments.json", {"limit": 5, "raw_json": 1})
    posts = []
    for x in ((comments or {}).get("data") or {}).get("children", []):
        a = x.get("data") or {}
        if x.get("kind") == "t1" and str(a.get("author", "")).casefold() == h.casefold():
            p = post(a.get("body"), "https://www.reddit.com" + a.get("permalink", ""), "r/" + a.get("subreddit", ""), a.get("created_utc"))
            if p:
                posts.append(p)
    return presence("Reddit", h, "https://www.reddit.com/user/" + quote(h), "Reddit public JSON",
                    bio=plain((u.get("subreddit") or {}).get("public_description")), since=day(u.get("created_utc")),
                    stats={"Comment karma": u.get("comment_karma")}, posts=posts[:5], activity_available=available)


def bluesky(h):
    c = PublicClient()
    actor = h if "." in h else h + ".bsky.social"
    u = c.get("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile", {"actor": actor})
    same_handle(u.get("handle"), actor)
    if not str(u.get("did", "")).startswith("did:"):
        raise Unavailable()
    feed, available = c.optional("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed", {"actor": u["did"], "limit": 10})
    posts = []
    for x in (feed or {}).get("feed", []):
        a = x.get("post") or {}
        if (a.get("author") or {}).get("did") != u["did"]:
            continue
        r = a.get("record") or {}
        uri = str(a.get("uri", ""))
        if not uri.startswith("at://" + u["did"] + "/app.bsky.feed.post/"):
            continue
        p = post(r.get("text"), "https://bsky.app/profile/" + quote(actor) + "/post/" + quote(uri.rsplit("/", 1)[-1]), "reply" if r.get("reply") else "post", r.get("createdAt"))
        if p:
            posts.append(p)
    return presence("Bluesky", actor, "https://bsky.app/profile/" + quote(actor), "Bluesky public AppView",
                    display_name=u.get("displayName"), bio=plain(u.get("description")),
                    stats={"Posts": u.get("postsCount"), "Followers": u.get("followersCount")},
                    declared=declared(*bio_links(u.get("description"))), posts=posts[:5], activity_available=available)


def mastodon(h):
    c = PublicClient()
    u = c.get("https://mastodon.social/api/v1/accounts/lookup", {"acct": h})
    same_handle(u.get("acct"), h)
    if not str(u.get("id", "")).isdigit():
        raise Unavailable()
    statuses, available = c.optional("https://mastodon.social/api/v1/accounts/" + u["id"] + "/statuses", {"limit": 5, "exclude_reblogs": "true"})
    posts = [post(s.get("content"), s.get("url"), "reply" if s.get("in_reply_to_id") else "post", s.get("created_at"))
             for s in statuses if not s.get("reblog") and s.get("visibility") in ("public", "unlisted")] if isinstance(statuses, list) else []
    fields = []
    for f in u.get("fields") or []:
        urls = bio_links(html.unescape(f.get("value") or ""))
        if urls and urls[0]:
            fields.append({**urls[0], "label": plain(f.get("name")), "verified": bool(f.get("verified_at"))})
    return presence("Mastodon (mastodon.social)", h + "@mastodon.social", safe_url(u.get("url")) or "https://mastodon.social/@" + quote(h), "mastodon.social public API",
                    display_name=u.get("display_name"), bio=plain(u.get("note")), since=day(u.get("created_at")),
                    stats={"Posts": u.get("statuses_count"), "Followers": u.get("followers_count")},
                    declared=declared(*fields, *bio_links(u.get("note"))), posts=[p for p in posts if p][:5], activity_available=available)


def dev(h):
    c = PublicClient()
    u = c.get("https://dev.to/api/users/by_username", {"url": h})
    same_handle(u.get("username"), h)
    articles, available = c.optional("https://dev.to/api/articles", {"username": h, "per_page": 5})
    posts = [post(a.get("title"), a.get("url"), "article", a.get("published_at")) for a in articles
             if str((a.get("user") or {}).get("username", "")).casefold() == h.casefold()] if isinstance(articles, list) else []
    return presence("DEV", h, "https://dev.to/" + quote(h), "DEV (Forem) public API", display_name=u.get("name"), bio=plain(u.get("summary")),
                    declared=declared(link(u.get("website_url")), link("https://github.com/" + quote(u["github_username"], safe=""), "GitHub") if u.get("github_username") else None,
                                      link("https://x.com/" + quote(u["twitter_username"], safe=""), "X") if u.get("twitter_username") else None),
                    posts=[p for p in posts if p][:5], activity_available=available)


ACTIVITY_SOURCES = {"GitHub": github, "Hacker News": hacker_news, "Reddit": reddit,
                    "Bluesky": bluesky, "Mastodon (mastodon.social)": mastodon, "DEV": dev}


def github_name(name):
    c = PublicClient()
    data = c.get("https://api.github.com/search/users", {"q": '"' + name + '" in:fullname', "per_page": 3})
    if not isinstance(data.get("items"), list):
        raise Unavailable()
    accounts = []
    for item in data["items"][:3]:
        if item.get("type") != "User" or not item.get("login"):
            continue
        u = c.get("https://api.github.com/users/" + quote(item["login"], safe=""))
        # Search ranking alone is not evidence the profile names this person.
        from modules.deep_search_plan import normalise
        if normalise(u.get("name") or "") != normalise(name):
            continue
        accounts.append({"platform": "GitHub", "handle": u["login"], "url": "https://github.com/" + quote(u["login"]),
                         "detail": plain(" · ".join(str(u[k]) for k in ("name", "company", "location", "bio") if u.get(k))),
                         "source": "GitHub full-name search", "candidate": True})
    return {"accounts": accounts}


def orcid_name(name):
    data = PublicClient().get("https://pub.orcid.org/v3.0/expanded-search/", {"q": '"' + name + '"', "rows": 5})
    rows = data.get("expanded-result")
    if rows is None and data.get("num-found") == 0:
        rows = []
    if not isinstance(rows, list):
        raise Unavailable()
    from modules.deep_search_plan import normalise
    accounts = []
    for row in rows:
        record_name = " ".join(str(row.get(k) or "") for k in ("given-names", "family-names"))
        identifier = row.get("orcid-id", "")
        if normalise(record_name) == normalise(name) and re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", identifier):
            accounts.append({"platform": "ORCID", "handle": identifier, "url": "https://orcid.org/" + identifier,
                             "detail": plain(record_name + " · " + ", ".join(row.get("institution-name") or [])),
                             "source": "ORCID public registry", "candidate": True})
    return {"accounts": accounts}


def wikidata_name(name):
    c = PublicClient()
    endpoint = "https://www.wikidata.org/w/api.php"
    search = c.get(endpoint, {"action": "wbsearchentities", "search": name, "language": "en", "format": "json", "limit": 7})
    ids = [x["id"] for x in search["search"] if re.fullmatch(r"Q\d+", x.get("id", ""))]
    if not ids:
        return {"people": []}
    data = c.get(endpoint, {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels|descriptions|sitelinks/urls", "languages": "en", "sitefilter": "enwiki", "format": "json"})
    fact_props = {"P106": "Occupation", "P108": "Employer", "P69": "Education", "P27": "Citizenship"}
    referenced = set()
    for ent in data["entities"].values():
        for prop in fact_props:
            for claim in (ent.get("claims") or {}).get(prop, [])[:3]:
                value = (claim.get("mainsnak") or {}).get("datavalue", {}).get("value")
                if isinstance(value, dict) and re.fullmatch(r"Q\d+", value.get("id", "")):
                    referenced.add(value["id"])
    labels = {}
    if referenced:
        entities = c.get(endpoint, {"action": "wbgetentities", "ids": "|".join(sorted(referenced)[:48]), "props": "labels", "languages": "en", "format": "json"})
        labels = {identifier: (ent.get("labels", {}).get("en") or {}).get("value") for identifier, ent in entities["entities"].items()}
    people = []
    socials = {"P6634": ("LinkedIn", "https://www.linkedin.com/in/"), "P2002": ("X", "https://x.com/"),
               "P2003": ("Instagram", "https://www.instagram.com/"), "P2037": ("GitHub", "https://github.com/"),
               "P2013": ("Facebook", "https://www.facebook.com/"), "P2397": ("YouTube", "https://www.youtube.com/channel/")}
    for identifier in ids:
        ent = data["entities"].get(identifier) or {}
        claims = ent.get("claims") or {}
        def values(prop):
            return [(x.get("mainsnak") or {}).get("datavalue", {}).get("value") for x in claims.get(prop, []) if x.get("rank") != "deprecated"]
        if not any(isinstance(v, dict) and v.get("id") == "Q5" for v in values("P31")):
            continue
        links = []
        for prop, (label, prefix) in socials.items():
            for v in values(prop)[:1]:
                if isinstance(v, str):
                    links.append(link(prefix + quote(v, safe=""), label))
        links.extend(link(v, "Official website") for v in values("P856") if isinstance(v, str))
        facts = {}
        for prop, label in fact_props.items():
            names = [labels[v["id"]] for v in values(prop)[:3] if isinstance(v, dict) and labels.get(v.get("id"))]
            if names:
                facts[label] = ", ".join(names)
        people.append({"name": (ent.get("labels", {}).get("en") or {}).get("value", name),
                       "description": (ent.get("descriptions", {}).get("en") or {}).get("value", ""),
                       "url": "https://www.wikidata.org/wiki/" + identifier, "source": "Wikidata human record",
                       "links": declared(*links), "facts": facts, "candidate": True})
    return {"people": people[:3]}


def keybase(h):
    data = PublicClient().get("https://keybase.io/_/api/1.0/user/lookup.json", {"usernames": h, "fields": "proofs_summary,basics,profile"})
    if (data.get("status") or {}).get("code") != 0 or not isinstance(data.get("them"), list):
        raise Unavailable()
    u = next((u for u in data["them"] if isinstance(u, dict)), None)
    if not u:
        raise Missing()
    same_handle((u.get("basics") or {}).get("username"), h)
    proofs = []
    for p in (u.get("proofs_summary") or {}).get("all", []):
        url = safe_url(p.get("service_url") or p.get("proof_url"))
        if url and p.get("nametag"):
            proofs.append({"platform": plain(p.get("proof_type")), "handle": plain(p["nametag"]), "url": url,
                           "is_alias": p["nametag"].casefold() != h.casefold()})
    return {"identity": {"username": h, "proofs": proofs, "url": "https://keybase.io/" + quote(h), "source": "Keybase published proofs"}}


NAME_SOURCES = {"Wikidata": wikidata_name, "GitHub full-name search": github_name, "ORCID": orcid_name}
