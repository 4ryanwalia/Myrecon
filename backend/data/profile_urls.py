"""
Profile-URL shapes — does a URL *name* an account, or merely mention one?

This is the answer to the "it said the account exists, but the link is dead"
problem. A dork like `site:github.com "bob"` matches every page on the domain
containing the word bob: issues, wikis, other people's repos, the marketing
site. Treating any github.com URL as bob's profile is how a result ends up
claiming an account that was never there.

So a URL is only a candidate profile when its *path shape* matches how the
platform actually addresses accounts (github.com/<handle>, reddit.com/user/
<handle>, medium.com/@<handle>), the segment in the handle position isn't a
reserved word the platform uses for its own pages, and — when we know who we
are looking for — that segment is the handle we searched.

That is still only a candidate. It says the URL is shaped like a profile, not
that the profile exists today; Google's index goes stale. services.search
fetches the survivors and verifies them before any of them are reported as
found. This module is the cheap filter that decides what is worth fetching.
"""

from urllib.parse import unquote, urlsplit

# ──────────────────────────────────────────────────────────────
#  Path templates
#
#  "{h}" marks the handle segment. A URL matches only when its
#  segment count equals the template's, so github.com/torvalds
#  is a profile and github.com/torvalds/linux is a repo page.
# ──────────────────────────────────────────────────────────────

PROFILE_PATHS: dict[str, tuple[str, ...]] = {
    # ── Social ────────────────────────────────────────────────
    "twitter.com":        ("/{h}",),
    "x.com":              ("/{h}",),
    "instagram.com":      ("/{h}",),
    "facebook.com":       ("/{h}", "/people/{h}", "/profile.php"),
    "tiktok.com":         ("/@{h}",),
    "threads.net":        ("/@{h}",),
    "threads.com":        ("/@{h}",),
    "bsky.app":           ("/profile/{h}",),
    "snapchat.com":       ("/add/{h}",),
    "pinterest.com":      ("/{h}",),
    "vk.com":             ("/{h}",),
    "ok.ru":              ("/{h}", "/profile/{h}"),
    "weibo.com":          ("/u/{h}", "/{h}"),
    "mastodon.social":    ("/@{h}",),
    "pixelfed.social":    ("/{h}", "/@{h}"),
    "misskey.io":         ("/@{h}",),
    "counter.social":     ("/@{h}",),
    "me.dm":              ("/@{h}",),
    "lemmy.world":        ("/u/{h}",),
    "lemmy.ml":           ("/u/{h}",),
    "kbin.social":        ("/u/{h}", "/m/{h}"),
    "truthsocial.com":    ("/@{h}",),
    "gab.com":            ("/{h}",),
    "gettr.com":          ("/user/{h}",),
    "minds.com":          ("/{h}",),
    "mewe.com":           ("/i/{h}",),
    "plurk.com":          ("/{h}",),
    "ello.co":            ("/{h}",),
    "cohost.org":         ("/{h}",),
    "myspace.com":        ("/{h}",),
    "tagged.com":         ("/{h}",),
    "skyrock.com":        ("/{h}",),
    "vero.co":            ("/{h}",),
    "mixi.jp":            ("/{h}",),
    "line.me":            ("/ti/p/{h}", "/R/ti/p/{h}"),

    # ── Link-in-bio / identity ────────────────────────────────
    "linktr.ee":          ("/{h}",),
    "bio.link":           ("/{h}",),
    "beacons.ai":         ("/{h}",),
    "solo.to":            ("/{h}",),
    "lnk.bio":            ("/{h}",),
    "allmylinks.com":     ("/{h}",),
    "about.me":           ("/{h}",),
    "gravatar.com":       ("/{h}",),
    "keybase.io":         ("/{h}",),
    "calendly.com":       ("/{h}",),
    "polywork.com":       ("/{h}",),
    "linkedin.com":       ("/in/{h}", "/company/{h}"),
    "xing.com":           ("/profile/{h}",),

    # ── Developer ─────────────────────────────────────────────
    "github.com":         ("/{h}",),
    "gist.github.com":    ("/{h}",),
    "gitlab.com":         ("/{h}", "/users/{h}"),
    "bitbucket.org":      ("/{h}",),
    "codeberg.org":       ("/{h}",),
    "gitee.com":          ("/{h}",),
    "sourcehut.org":      ("/~{h}",),
    "sr.ht":              ("/~{h}",),
    "pagure.io":          ("/user/{h}",),
    "launchpad.net":      ("/~{h}",),
    "sourceforge.net":    ("/u/{h}",),
    "giters.com":         ("/{h}",),
    "stackoverflow.com":  ("/users/{h}",),
    "stackexchange.com":  ("/users/{h}",),
    "superuser.com":      ("/users/{h}",),
    "serverfault.com":    ("/users/{h}",),
    "askubuntu.com":      ("/users/{h}",),
    "dev.to":             ("/{h}",),
    "hashnode.com":       ("/@{h}",),
    "medium.com":         ("/@{h}",),
    "codepen.io":         ("/{h}",),
    "codesandbox.io":     ("/u/{h}",),
    "stackblitz.com":     ("/@{h}",),
    "replit.com":         ("/@{h}",),
    "repl.it":            ("/@{h}",),
    "glitch.com":         ("/@{h}",),
    "jsfiddle.net":       ("/user/{h}",),
    "observablehq.com":   ("/@{h}",),
    "coderwall.com":      ("/{h}",),
    "gitconnected.com":   ("/{h}",),
    "npmjs.com":          ("/~{h}",),
    "pypi.org":           ("/user/{h}",),
    "rubygems.org":       ("/profiles/{h}",),
    "crates.io":          ("/users/{h}",),
    "packagist.org":      ("/users/{h}",),
    "nuget.org":          ("/profiles/{h}",),
    "hex.pm":             ("/users/{h}",),
    "metacpan.org":       ("/author/{h}",),
    "hub.docker.com":     ("/u/{h}",),
    "quay.io":            ("/user/{h}",),
    "huggingface.co":     ("/{h}",),
    "kaggle.com":         ("/{h}",),
    "leetcode.com":       ("/{h}", "/u/{h}"),
    "hackerrank.com":     ("/{h}", "/profile/{h}"),
    "hackerearth.com":    ("/@{h}", "/users/{h}"),
    "codeforces.com":     ("/profile/{h}",),
    "codechef.com":       ("/users/{h}",),
    "atcoder.jp":         ("/users/{h}",),
    "topcoder.com":       ("/members/{h}",),
    "codewars.com":       ("/users/{h}",),
    "exercism.org":       ("/profiles/{h}",),
    "kattis.com":         ("/users/{h}",),
    "csacademy.com":      ("/user/{h}",),
    "rosalind.info":      ("/users/{h}",),
    "geeksforgeeks.org":  ("/user/{h}",),
    "codingninjas.com":   ("/profile/{h}",),
    "devpost.com":        ("/{h}",),
    "frontendmentor.io":  ("/profile/{h}",),
    "indiehackers.com":   ("/{h}",),
    "producthunt.com":    ("/@{h}",),
    "lobste.rs":          ("/u/{h}",),
    "news.ycombinator.com": ("/user",),
    "readthedocs.org":    ("/profiles/{h}",),

    # ── Security ──────────────────────────────────────────────
    "hackerone.com":      ("/{h}", "/users/{h}"),
    "bugcrowd.com":       ("/{h}",),
    "intigriti.com":      ("/profile/{h}", "/researcher/{h}"),
    "yeswehack.com":      ("/hunters/{h}",),
    "hackthebox.com":     ("/users/{h}", "/profile/{h}"),
    "app.hackthebox.com": ("/users/{h}", "/profile/{h}"),
    "tryhackme.com":      ("/p/{h}", "/r/p/{h}"),
    "root-me.org":        ("/{h}",),
    "ctftime.org":        ("/user/{h}", "/team/{h}"),
    "exploit-db.com":     ("/author/{h}",),
    "letsdefend.io":      ("/profile/{h}",),
    "blueteamlabs.online": ("/profile/{h}",),
    "cyberdefenders.org": ("/p/{h}",),

    # ── Video / audio ─────────────────────────────────────────
    "youtube.com":        ("/@{h}", "/c/{h}", "/user/{h}", "/channel/{h}"),
    "twitch.tv":          ("/{h}",),
    "kick.com":           ("/{h}",),
    "rumble.com":         ("/user/{h}", "/c/{h}"),
    "odysee.com":         ("/@{h}",),
    "vimeo.com":          ("/{h}",),
    "dailymotion.com":    ("/{h}",),
    "bitchute.com":       ("/channel/{h}",),
    "floatplane.com":     ("/channel/{h}",),
    "soundcloud.com":     ("/{h}",),
    "mixcloud.com":       ("/{h}",),
    "audiomack.com":      ("/{h}",),
    "hearthis.at":        ("/{h}",),
    "bandlab.com":        ("/{h}",),
    "beatstars.com":      ("/{h}",),
    "reverbnation.com":   ("/{h}",),
    "smule.com":          ("/{h}",),
    "last.fm":            ("/user/{h}",),
    "genius.com":         ("/{h}",),
    "discogs.com":        ("/user/{h}",),
    "rateyourmusic.com":  ("/~{h}",),
    "musicbrainz.org":    ("/user/{h}",),
    "open.spotify.com":   ("/user/{h}", "/artist/{h}"),
    "podchaser.com":      ("/creators/{h}",),
    "player.fm":          ("/{h}",),
    "anchor.fm":          ("/{h}",),
    "podbean.com":        ("/{h}",),
    "spreaker.com":       ("/user/{h}",),

    # ── Support / commerce ────────────────────────────────────
    "patreon.com":        ("/{h}",),
    "ko-fi.com":          ("/{h}",),
    "buymeacoffee.com":   ("/{h}",),
    "gumroad.com":        ("/{h}",),
    "fanbox.cc":          ("/@{h}",),
    "etsy.com":           ("/shop/{h}",),
    "ebay.com":           ("/usr/{h}",),
    "poshmark.com":       ("/closet/{h}",),
    "depop.com":          ("/{h}",),
    "redbubble.com":      ("/people/{h}",),
    "society6.com":       ("/{h}",),
    "zazzle.com":         ("/store/{h}", "/{h}"),
    "teepublic.com":      ("/user/{h}",),

    # ── Art / photo / design ──────────────────────────────────
    "behance.net":        ("/{h}",),
    "dribbble.com":       ("/{h}",),
    "artstation.com":     ("/{h}",),
    "deviantart.com":     ("/{h}",),
    "newgrounds.com":     ("/{h}",),
    "furaffinity.net":    ("/user/{h}",),
    "pixiv.net":          ("/users/{h}", "/en/users/{h}"),
    "flickr.com":         ("/people/{h}", "/photos/{h}"),
    "500px.com":          ("/p/{h}", "/{h}"),
    "unsplash.com":       ("/@{h}",),
    "pexels.com":         ("/@{h}",),
    "imgur.com":          ("/user/{h}",),
    "vsco.co":            ("/{h}",),
    "giphy.com":          ("/{h}",),
    "weheartit.com":      ("/{h}",),
    "coroflot.com":       ("/{h}",),
    "figma.com":          ("/@{h}",),
    "artwanted.com":      ("/{h}",),

    # ── Writing / reading ─────────────────────────────────────
    "substack.com":       ("/@{h}",),
    "wattpad.com":        ("/user/{h}",),
    "archiveofourown.org": ("/users/{h}",),
    "fanfiction.net":     ("/u/{h}",),
    "fictionpress.com":   ("/u/{h}",),
    "royalroad.com":      ("/profile/{h}",),
    "scribblehub.com":    ("/profile/{h}",),
    "inkitt.com":         ("/{h}",),
    "allpoetry.com":      ("/{h}",),
    "goodreads.com":      ("/user/show/{h}", "/{h}"),
    "librarything.com":   ("/profile/{h}",),
    "storygraph.com":     ("/profile/{h}",),
    "letterboxd.com":     ("/{h}",),
    "trakt.tv":           ("/users/{h}",),
    "myanimelist.net":    ("/profile/{h}",),
    "micro.blog":         ("/{h}",),
    "write.as":           ("/{h}",),
    "telegra.ph":         ("/{h}",),
    "scribd.com":         ("/{h}", "/user/{h}"),
    "slideshare.net":     ("/{h}",),
    "issuu.com":          ("/{h}",),

    # ── Forums ────────────────────────────────────────────────
    "reddit.com":         ("/user/{h}", "/u/{h}"),
    "quora.com":          ("/profile/{h}",),
    "disqus.com":         ("/by/{h}",),
    "meta.discourse.org": ("/u/{h}",),
    "forum.xda-developers.com": ("/m/{h}", "/members/{h}"),
    "xdaforums.com":      ("/m/{h}", "/members/{h}"),
    "forums.macrumors.com": ("/members/{h}",),
    "forums.anandtech.com": ("/members/{h}",),
    "linustechtips.com":  ("/profile/{h}",),
    "ubuntuforums.org":   ("/member.php",),

    # ── Gaming ────────────────────────────────────────────────
    "steamcommunity.com": ("/id/{h}", "/profiles/{h}"),
    "itch.io":            ("/{h}",),
    "gamejolt.com":       ("/@{h}",),
    "moddb.com":          ("/members/{h}",),
    "nexusmods.com":      ("/users/{h}",),
    "curseforge.com":     ("/members/{h}",),
    "planetminecraft.com": ("/member/{h}",),
    "namemc.com":         ("/profile/{h}",),
    "chess.com":          ("/member/{h}",),
    "lichess.org":        ("/@/{h}",),
    "osu.ppy.sh":         ("/users/{h}",),
    "speedrun.com":       ("/users/{h}", "/user/{h}"),
    "faceit.com":         ("/en/players/{h}", "/players/{h}"),
    "op.gg":              ("/summoners/{h}",),
    "warcraftlogs.com":   ("/users/{h}",),
    "raider.io":          ("/users/{h}",),
    "boardgamearena.com": ("/player",),
    "roblox.com":         ("/users/{h}/profile",),
    "tracker.gg":         ("/profile/{h}",),

    # ── Academic ──────────────────────────────────────────────
    "researchgate.net":   ("/profile/{h}",),
    "academia.edu":       ("/{h}",),
    "orcid.org":          ("/{h}",),
    "semanticscholar.org": ("/author/{h}",),
    "osf.io":             ("/profiles/{h}",),
    "figshare.com":       ("/authors/{h}",),
    "openreview.net":     ("/profile",),
    "loop.frontiersin.org": ("/people/{h}",),
    "arxiv.org":          ("/a/{h}",),

    # ── Work / freelance ──────────────────────────────────────
    "upwork.com":         ("/freelancers/{h}",),
    "fiverr.com":         ("/{h}", "/users/{h}"),
    "freelancer.com":     ("/u/{h}",),
    "peopleperhour.com":  ("/freelancer/{h}",),
    "guru.com":           ("/freelancers/{h}",),
    "workana.com":        ("/freelancer/{h}",),
    "contra.com":         ("/{h}",),
    "toptal.com":         ("/resume/{h}",),
    "wellfound.com":      ("/u/{h}",),
    "angel.co":           ("/u/{h}",),
    "crunchbase.com":     ("/person/{h}",),
    "clutch.co":          ("/profile/{h}",),
    "meetup.com":         ("/members/{h}",),
    "sessionize.com":     ("/{h}",),
    "speakerhub.com":     ("/speaker/{h}",),

    # ── Learning ──────────────────────────────────────────────
    "duolingo.com":       ("/profile/{h}",),
    "codecademy.com":     ("/profiles/{h}",),
    "freecodecamp.org":   ("/{h}",),
    "khanacademy.org":    ("/profile/{h}",),
    "skillshare.com":     ("/user/{h}", "/profile/{h}"),
    "instructables.com":  ("/member/{h}",),
    "hackaday.io":        ("/{h}",),

    # ── Travel / reviews / fitness ────────────────────────────
    "tripadvisor.com":    ("/Profile/{h}", "/members/{h}"),
    "tripoto.com":        ("/profile/{h}",),
    "travellerspoint.com": ("/members/{h}",),
    "couchsurfing.com":   ("/people/{h}",),
    "airbnb.com":         ("/users/show/{h}",),
    "yelp.com":           ("/user_details",),
    "foursquare.com":     ("/user/{h}",),
    "trustpilot.com":     ("/users/{h}",),
    "strava.com":         ("/athletes/{h}",),
    "myfitnesspal.com":   ("/profile/{h}",),
    "runkeeper.com":      ("/user/{h}",),
    "mapmyrun.com":       ("/profile/{h}",),
    "mapmyride.com":      ("/profile/{h}",),
    "trainingpeaks.com":  ("/athletes/{h}",),
    "athlinks.com":       ("/athletes/{h}",),
    "boxrec.com":         ("/en/proboxer/{h}",),
    "ufc.com":            ("/athlete/{h}",),

    # ── Crypto ────────────────────────────────────────────────
    "opensea.io":         ("/{h}",),
    "rarible.com":        ("/{h}",),
    "foundation.app":     ("/@{h}",),
    "mirror.xyz":         ("/{h}",),
    "debank.com":         ("/profile/{h}",),
    "zapper.xyz":         ("/account/{h}",),
    "gitcoin.co":         ("/{h}",),
    "tradingview.com":    ("/u/{h}",),
    "coinmarketcap.com":  ("/community/profile/{h}",),

    # ── Messaging / paste ─────────────────────────────────────
    "t.me":               ("/{h}",),
    "telegram.me":        ("/{h}",),
    "pastebin.com":       ("/u/{h}",),
    "rentry.co":          ("/{h}",),
    "justpaste.it":       ("/{h}",),
}

# Hosts where the handle is the subdomain rather than a path segment.
HANDLE_SUBDOMAINS: frozenset = frozenset({
    "tumblr.com", "substack.com", "wordpress.com", "blogspot.com",
    "livejournal.com", "bandcamp.com", "carrd.co", "notion.site",
    "ghost.io", "hashnode.dev", "medium.com", "itch.io", "newgrounds.com",
    "deviantart.com", "bearblog.dev", "micro.blog", "gitbook.io",
})

# Segments that sit in the handle position but belong to the platform, not to
# a person. Without this every `github.com/features` or `twitter.com/explore`
# hit reads as a profile.
RESERVED_HANDLES: frozenset = frozenset({
    "", "www", "m", "en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh",
    "about", "abuse", "account", "accounts", "ads", "advertise", "ai", "api",
    "app", "apps", "archive", "article", "articles", "auth", "blog", "blogs",
    "board", "brand", "business", "careers", "cart", "categories", "category",
    "channel", "channels", "chat", "checkout", "cloud", "collection",
    "collections", "comment", "comments", "community", "companies", "company",
    "compare", "contact", "content", "cookie", "cookies", "corporate",
    "courses", "create", "creator", "dashboard", "developer", "developers",
    "digital", "directory", "discover", "docs", "documentation", "download",
    "downloads", "edit", "editor", "education", "enterprise", "events",
    "explore", "faq", "features", "feed", "feedback", "files", "forum",
    "forums", "gallery", "get", "gift", "group", "groups", "guide", "guides",
    "hashtag", "help", "home", "hot", "how", "i", "images", "index", "info",
    "insights", "install", "intent", "invite", "jobs", "join", "learn",
    "legal", "library", "license", "links", "list", "lists", "live", "login",
    "logout", "magazine", "mail", "main", "map", "maps", "marketing",
    "marketplace", "media", "members", "menu", "message", "messages", "mobile",
    "more", "my", "new", "news", "newsletter", "notifications", "offers",
    "onboarding", "opensource", "order", "orders", "p", "page", "pages",
    "partner", "partners", "password", "payment", "photo", "photos", "plans",
    "platform", "podcast", "podcasts", "policies", "policy", "post", "posts",
    "premium", "press", "pricing", "privacy", "product", "products", "profile",
    "profiles", "projects", "pulse", "questions", "read", "recent",
    "redirect", "register", "release", "releases", "reset", "resources",
    "results", "reviews", "roadmap", "rss", "s", "sale", "search", "security",
    "services", "session", "settings", "share", "shop",
    "shopping", "showcase", "signin", "signup", "sitemap", "solutions",
    "source", "sponsors", "start", "static", "status", "store", "stories",
    "story", "subscribe", "support", "tag", "tags", "team", "teams", "terms",
    "test", "themes", "topic", "topics", "tos", "tour", "trending", "tv",
    "u", "upgrade", "upload", "user", "users", "video", "videos", "view",
    "wallet", "watch", "web", "welcome", "wiki", "work", "world", "write",
})

_SEPARATORS = ("-", "_", ".")


def _host_of(url: str) -> str:
    host = urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _segments(url: str) -> list:
    path = urlsplit(url).path
    return [unquote(s) for s in path.split("/") if s]


def _match_template(template: str, segs: list) -> str:
    """Return the handle if `segs` fits `template`, else ''."""
    parts = [p for p in template.split("/") if p]
    if len(parts) != len(segs):
        return ""
    handle = ""
    for want, got in zip(parts, segs):
        if "{h}" in want:
            prefix, suffix = want.split("{h}", 1)
            if not got.startswith(prefix) or not got.endswith(suffix):
                return ""
            handle = got[len(prefix):len(got) - len(suffix) if suffix else None]
            if not handle:
                return ""
        elif want.lower() != got.lower():
            return ""
    # A template with no {h} (facebook profile.php?id=…, hn /user?id=…) is a
    # profile URL whose handle lives in the query string; report the shape but
    # no handle, and let the caller decide.
    return handle or "?"


# Leading labels that are the same site, not a different product. Anything
# else (blog.github.com, help.twitter.com) is deliberately *not* folded into
# the parent — its paths are articles, not accounts.
_NEUTRAL_PREFIXES = frozenset({
    "m", "mobile", "touch", "amp", "old", "new", "np", "web", "www2",
    "en", "en-gb", "en-us", "de", "fr", "es", "it", "pt", "nl", "ja", "ru",
})


def _lookup(host: str) -> tuple:
    """Templates for `host`, folding away locale/mobile prefixes only."""
    if host in PROFILE_PATHS:
        return PROFILE_PATHS[host]
    head, _, rest = host.partition(".")
    if head in _NEUTRAL_PREFIXES and rest in PROFILE_PATHS:
        return PROFILE_PATHS[rest]
    return ()


def profile_handle(url: str):
    """
    ``(domain, handle)`` when `url` is shaped like an account page, else None.

    ``handle`` is ``"?"`` for platforms that key profiles off a query string
    (facebook.com/profile.php?id=…), meaning "profile-shaped, handle unknown".
    """
    if not url or not url.startswith(("http://", "https://")):
        return None
    host = _host_of(url)
    if not host:
        return None

    # {handle}.tumblr.com and friends: the subdomain is the account.
    parts = host.split(".")
    if len(parts) > 2:
        base = ".".join(parts[1:])
        if base in HANDLE_SUBDOMAINS and parts[0] not in RESERVED_HANDLES:
            return base, parts[0]

    templates = _lookup(host)
    if not templates:
        return None

    segs = _segments(url)
    for template in templates:
        handle = _match_template(template, segs)
        if not handle:
            continue
        if handle != "?" and handle.lower().lstrip("@~") in RESERVED_HANDLES:
            return None
        return host, handle
    return None


def is_profile_url(url: str) -> bool:
    """True when the URL is shaped like somebody's account page."""
    return profile_handle(url) is not None


def handles_match(handle: str, target: str) -> bool:
    """
    Does `handle` (lifted out of a URL) name the account we searched for?

    Exact after case folding and @/~ stripping, plus the one loose case worth
    allowing: platforms that append a disambiguator to the slug they hand out
    (linkedin.com/in/jane-doe-8b41a2 for jane-doe). The separator is required,
    so `janedoe99` never matches `janedoe`.
    """
    if not handle or not target or handle == "?":
        return False
    h = handle.lower().lstrip("@~").rstrip("/")
    t = target.lower().lstrip("@~").strip()
    if not t or " " in t:
        return False
    if h == t:
        return True
    return any(h.startswith(t + sep) for sep in _SEPARATORS)
