"""
Maigret's site list, admitted to the website's full scan only through the
website's own verdict engine.

tools/maigret_harness.py asked a looser question (do a real and an impossible
handle get *different* pages?). This one asks the question the sweep itself
asks: run modules.sweep.Sweep.probe(), the port of the app's
UsernameSweep.probe(), and a site is admitted only if

  * Maigret's known-real handle comes back FOUND, and
  * Maigret's known-unclaimed handle does NOT come back FOUND, and
  * a fresh 12-letter impossible handle does NOT come back FOUND.

So an admitted site is one the engine can already prove an account on and
already refuses to invent one for. Maigret's presence/absence strings are not
imported as evidence: most are generic ("og:title", "displayName") and would
be exactly the mentions-the-handle shortcut the app forbids. Only the profile
URL, status conventions and the username regex come across.

    python tools/maigret_web_import.py --data ../trythese.txt --probe --emit

Output: tools/out/web_import_results.json (every verdict) and
backend/data/platforms_extra.json (the survivors) when --emit is given.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, "backend")
OUT = os.path.join(HERE, "out")
sys.path.insert(0, BACKEND)

from modules import sweep as S  # noqa: E402

# Adult and dating listings stay out: the site carries AdSense, and a scan
# result is shown and shared with a link to every platform in it.
SKIP_TAGS = {"porn", "sex", "adult", "nsfw", "erotic", "dating", "18+", "webcam"}

CATEGORY = [
    ("Social", {"social", "networking", "blog", "messaging"}),
    ("Developer", {"coding", "tech", "it", "programming", "hacking", "cybersecurity"}),
    ("Gaming", {"gaming", "games", "game"}),
    ("Forum", {"forum", "discussion", "board", "q&a"}),
    ("Media", {"video", "streaming", "music", "photo", "images", "art", "design"}),
    ("Knowledge", {"wiki", "education", "science", "news", "books", "reading"}),
    ("Business", {"business", "finance", "shopping", "freelance", "jobs", "crypto"}),
]


def host_of(url: str) -> str:
    try:
        h = urlparse(url.replace("{username}", "x")).netloc.lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def category_for(tags) -> str:
    t = set(tags or [])
    for name, keys in CATEGORY:
        if t & keys:
            return name
    return "Other"


# Maigret "engines" are software families. These are the same families the
# app's PlatformCatalogue builds with discourse() / mastodon() / lemmy() /
# gitlabAt() / gitea(), and each maps to the exact entry shape those helpers
# export: an API that answers with a user object, checked for one field.
FAMILIES = {
    "DiscourseJson": ("{m}/u/{username}", "{m}/u/{username}.json", '"username"', None, "Forum"),
    "Discourse": ("{m}/u/{username}", "{m}/u/{username}.json", '"username"', None, "Forum"),
    "Mastodon": ("{m}/@{username}", "{m}/api/v1/accounts/lookup?acct={username}", '"acct"', None, "Social"),
    "Lemmy": ("{m}/u/{username}", "{m}/api/v3/user?username={username}", '"person"', None, "Forum"),
    "GitLab": ("{m}/{username}", "{m}/api/v4/users?username={username}", '"username"', None, "Developer"),
    "Gitea": ("{m}/{username}", "{m}/api/v1/users/{username}", '"login"', None, "Developer"),
}
_WIKI_API = {"MediaWikiJson": "", "MediaWikiJson/w": "/w", "MediaWikiJson/wiki": "/wiki",
             "MediaWikiJson/mediawiki": "/mediawiki"}


def _family(engine: str, s: dict):
    main = (s.get("urlMain") or "").rstrip("/")
    if not main.startswith("https://") or s.get("url") or s.get("urlProbe"):
        return None
    if engine in FAMILIES:
        url, api, ok, missing, cat = FAMILIES[engine]
    elif engine in _WIKI_API:
        sub = s.get("urlSubpath") or ""
        url = "{m}" + sub + "/User:{username}"
        api = "{m}" + _WIKI_API[engine] + "/api.php?action=query&list=users&ususers={username}&format=json"
        ok, missing, cat = '"userid"', '"missing"', "Knowledge"
    else:
        return None
    return url.replace("{m}", main), api.replace("{m}", main), ok, missing, cat


def candidates(sites: dict) -> tuple[list[dict], Counter]:
    have_hosts = {host_of(p["url"]) for p in S.CATALOGUE}
    have_names = {p["name"].strip().lower() for p in S.CATALOGUE}
    why = Counter()
    out, seen = [], set()
    for name, s in sites.items():
        url = s.get("url") or ""
        if s.get("disabled"):
            why["disabled"] += 1; continue
        fam = _family(s["engine"], s) if s.get("engine") else None
        api = api_ok = api_missing = None
        if fam:
            url, api, api_ok, api_missing, fam_cat = fam
        elif "{username}" not in url or s.get("engine") or "{urlMain}" in url or "{urlSubpath}" in url:
            why["no plain template"] += 1; continue
        if not url.startswith("https://"):
            why["not https"] += 1; continue
        if not fam and (s.get("urlProbe") or s.get("headers") or s.get("type")):
            # A separate probe URL, custom headers or a non-username identifier
            # means the plain profile page is not what Maigret checks.
            why["needs special request"] += 1; continue
        tags = set(s.get("tags") or [])
        if tags & SKIP_TAGS:
            why["adult"] += 1; continue
        h = host_of(url)
        if not h or h in have_hosts or name.strip().lower() in have_names or h in seen:
            why["already have"] += 1; continue
        if not (s.get("usernameClaimed") and s.get("usernameUnclaimed")):
            why["no control pair"] += 1; continue
        seen.add(h)
        out.append({
            "name": name.strip(),
            "url": url,
            "ok_status": 200,
            "category": fam_cat if fam and category_for(tags) == "Other" else category_for(tags),
            "api": api, "api_headers": {}, "html_headers": {},
            "exists": None, "missing": None, "missing_status": 404,
            "api_exists": api_ok, "api_missing": api_missing,
            "echoes_handle": False,
            "regex_check": s.get("regexCheck") or None,
            "_claimed": s["usernameClaimed"],
            "_unclaimed": s["usernameUnclaimed"],
        })
    return out, why


def _verdict(p: dict, handle: str) -> dict:
    sw = S.Sweep(handle, deadline_seconds=120)
    try:
        return sw.probe(p)
    finally:
        sw.session.close()


def check(p: dict) -> dict:
    entry = {k: v for k, v in p.items() if not k.startswith("_")}
    out = {"name": p["name"], "url": p["url"]}
    try:
        real = _verdict(entry, p["_claimed"])
        out["claimed"] = f'{real["verdict"]}:{real["reason_code"]}'
        if real["verdict"] != S.FOUND:
            out["pass"] = False
            return out
        time.sleep(0.3 + random.random() * 0.4)
        fake = _verdict(entry, p["_unclaimed"])
        out["unclaimed"] = f'{fake["verdict"]}:{fake["reason_code"]}'
        impossible = "".join(random.choice(string.ascii_lowercase) for _ in range(12))
        ctrl = _verdict(entry, impossible)
        out["impossible"] = f'{ctrl["verdict"]}:{ctrl["reason_code"]}'
        out["pass"] = fake["verdict"] != S.FOUND and ctrl["verdict"] != S.FOUND
    except Exception as e:  # noqa: BLE001
        out["claimed"] = f"error:{type(e).__name__}"
        out["pass"] = False
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="a Maigret-format data.json")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()

    raw = json.load(open(a.data, encoding="utf-8"))
    sites = raw.get("sites", raw)
    cands, why = candidates(sites)
    print(f"{len(sites)} entries, {len(S.CATALOGUE)} already in the web catalogue")
    for k, n in why.most_common():
        print(f"  skipped {k:24} {n}")
    print(f"  -> {len(cands)} candidates")
    if not a.probe:
        return
    if a.limit:
        random.seed(7)
        cands = random.sample(cands, min(a.limit, len(cands)))

    os.makedirs(OUT, exist_ok=True)
    by_name = {c["name"]: c for c in cands}
    results, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(check, c) for c in cands]), 1):
            results.append(f.result())
            if i % 100 == 0 or i == len(cands):
                print(f"  {i}/{len(cands)} passed={sum(r['pass'] for r in results)} "
                      f"({time.time() - t0:.0f}s)", flush=True)

    json.dump(results, open(os.path.join(OUT, "web_import_results.json"), "w", encoding="utf-8"), indent=1)
    print("\nclaimed-handle verdicts:")
    for k, n in Counter(r["claimed"] for r in results).most_common(12):
        print(f"  {k:32} {n}")
    fp = [r for r in results if r["claimed"].startswith("found") and not r["pass"]]
    print(f"\nrejected for reporting an impossible handle as found: {len(fp)}")

    passed = sorted((by_name[r["name"]] for r in results if r["pass"]),
                    key=lambda p: (p["category"], p["name"].lower()))
    print(f"passed: {len(passed)}")
    if a.emit:
        rows = [{k: v for k, v in p.items() if not k.startswith("_")} for p in passed]
        dest = os.path.join(BACKEND, "data", "platforms_extra.json")
        json.dump(rows, open(dest, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
