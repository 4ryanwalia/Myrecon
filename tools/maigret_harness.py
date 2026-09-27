"""
Maigret's site list, put through MyRecon's own verdict test.

Maigret ships ~5,400 active sites under an MIT licence, which is a tempting
shortcut to a bigger catalogue. It is not one, because 61% of the entries new
to us decide existence by status code alone -- "200 means the account is
there" -- which is precisely the model the sweep exists to refuse. Importing
that wholesale would import a thousand sites' worth of the false positives
PlatformCatalogue was hand-built to avoid.

What makes the list usable anyway is that essentially every entry carries a
`usernameClaimed` and a `usernameUnclaimed`: a handle the author verified
exists, and one nobody could own. That is a control pair, already written, per
site -- so we never have to trust Maigret's detection. We run our own
differential probe against their two handles and keep only the sites that
answer the two *differently*.

That is the same test `UsernameSweep.controlShape` applies on the phone, run
here instead so the phone never pays for it.

    python tools/maigret_harness.py --fetch --probe --emit

Output lands in tools/out/ : a JSON report, and Kotlin for the sites that
passed. Nothing here writes into app/ -- review the report first.

**Read the verdicts as a floor, not a measurement.** This runs from one
laptop, and a laptop is on the wrong side of exactly the datacentre-vs-mobile
gap documented in PlatformCatalogue: a site that rate-limits this machine is
recorded UNREACHABLE here and may well answer a handset perfectly. Sites are
rejected for answering *identically* to both handles, which is a property of
the site, never for failing to answer us.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DATA_URL = "https://raw.githubusercontent.com/soxoj/maigret/main/maigret/resources/data.json"

CATALOGUES = [
    "app/src/main/java/com/aryan/myrecon/data/PlatformCatalogue.kt",
    "app/src/main/java/com/aryan/myrecon/data/PlatformCatalogueExtended.kt",
]

# One browser UA. Not evasion -- a default python-requests UA is refused by a
# large share of sites outright, which would record their behaviour as
# UNREACHABLE and tell us nothing about whether they discriminate.
UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")

TIMEOUT = 12
BODY_CAP = 60_000


# --------------------------------------------------------------------------
# the catalogue we already have
# --------------------------------------------------------------------------

ENTRY_PATTERNS = [
    r'\bP\(\s*"([^"]+)"\s*,\s*"(https?://[^"]+)"',
    r'\bp\(\s*"([^"]+)"\s*,\s*"(https?://[^"]+)"',
    r'PlatformDef\(\s*\n?\s*name\s*=\s*"([^"]+)"\s*,\s*\n?\s*template\s*=\s*"(https?://[^"]+)"',
    r'\bp\(\s*name\s*=\s*"([^"]+)"\s*,\s*url\s*=\s*"(https?://[^"]+)"',
]

# The family helpers — discourse("Arduino Forum", "forum.arduino.cc") and the
# mastodon/gitea/gitlab equivalents — take a bare host instead of a template,
# so the patterns above miss them entirely. That is 43 platforms, and missing
# them means neither their host nor their name is deduped: the first run of
# this harness imported five sites that already existed under the same name,
# which the catalogue test caught.
FAMILY_PATTERN = r'\b(?:discourse|mastodon|gitea|gitlabAt|lemmy|forgejo)\(\s*"([^"]+)"\s*,\s*"([a-z0-9][a-z0-9.\-]*\.[a-z]{2,})"'


def host_of(url: str) -> str:
    try:
        h = urlparse(url.replace("{username}", "x")).netloc.lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def existing(root: str) -> tuple[set[str], set[str]]:
    """(hosts, lowercased names) already in the app catalogue."""
    hosts, names = set(), set()
    for rel in CATALOGUES:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            print(f"  ! missing {rel}", file=sys.stderr)
            continue
        src = open(path, encoding="utf-8").read()
        for pat in ENTRY_PATTERNS:
            for m in re.finditer(pat, src):
                names.add(m.group(1).strip().lower())
                h = host_of(m.group(2))
                if h:
                    hosts.add(h)
        for m in re.finditer(FAMILY_PATTERN, src):
            names.add(m.group(1).strip().lower())
            h = m.group(2).lower()
            hosts.add(h[4:] if h.startswith("www.") else h)
    return hosts, names


# --------------------------------------------------------------------------
# candidates
# --------------------------------------------------------------------------

def fetch(force: bool = False) -> dict:
    os.makedirs(OUT, exist_ok=True)
    cache = os.path.join(OUT, "maigret-data.json")
    if force or not os.path.exists(cache):
        print("fetching maigret data.json ...")
        r = requests.get(DATA_URL, headers={"User-Agent": "myrecon-catalogue-harness"}, timeout=120)
        r.raise_for_status()
        open(cache, "wb").write(r.content)
    raw = json.load(open(cache, encoding="utf-8"))
    return raw.get("sites", raw)


def candidates(sites: dict, hosts: set[str], names: set[str], langs: set[str] | None) -> list[dict]:
    """
    Sites worth probing: active, not already ours, and carrying a control pair.

    `langs` drops entries tagged for a language market we are not in. It is a
    coverage decision, not a quality one -- a Russian forum board is a fine
    site, it is just unlikely to hold an account belonging to someone checking
    their own handle from India. Pass --all-langs to keep everything.
    """
    out = []
    for name, s in sites.items():
        if s.get("disabled"):
            continue
        url = s.get("url") or ""
        if "{username}" not in url:
            continue
        if not url.startswith("https://"):
            # A plaintext template cannot ship: the app sets
            # android:usesCleartextTraffic="false", so every one of these
            # would fail at the socket and record as UNKNOWN forever.
            continue
        h = host_of(url)
        if not h or h in hosts or name.strip().lower() in names:
            continue
        if not (s.get("usernameClaimed") and s.get("usernameUnclaimed")):
            continue
        tags = [t for t in (s.get("tags") or [])]
        if langs is not None:
            lang = [t for t in tags if t in LANG_TAGS]
            if lang and not (set(lang) & langs):
                continue
        out.append({
            "name": name,
            "url": url,
            "host": h,
            "claimed": s["usernameClaimed"],
            "unclaimed": s["usernameUnclaimed"],
            "checkType": s.get("checkType", "(none)"),
            "tags": tags,
        })
    return out


LANG_TAGS = {
    "ru", "ua", "de", "fr", "cn", "jp", "pl", "nl", "es", "it", "br", "kr",
    "tr", "cz", "fi", "se", "no", "dk", "hu", "ro", "gr", "il", "ir", "vn",
    "th", "id", "pt", "at", "ch", "be", "kz", "by", "rs", "hr", "bg", "sk",
}
# Markets the app is actually in. Untagged entries are treated as
# international and always kept.
KEEP_LANGS = {"us", "gb", "in", "au", "ca"}


# --------------------------------------------------------------------------
# the differential probe
# --------------------------------------------------------------------------

def shape(resp: requests.Response, handle: str) -> tuple:
    """
    A response reduced to what is comparable between two handles.

    The handle itself is stripped before measuring, because every page echoes
    the requested name somewhere -- in the title, the canonical URL, an error
    message -- and leaving it in makes two identical pages look different for
    the one reason that proves nothing. This mirrors what `controlShape` does
    on the device.

    Length is bucketed rather than exact: a timestamp, a CSRF token or a
    rotating ad slot moves a byte count between two requests to the *same*
    page, and an exact comparison would read that as evidence.
    """
    body = (resp.text or "")[:BODY_CAP]
    body = re.sub(re.escape(handle), "", body, flags=re.I)
    body = re.sub(r"\s+", " ", body).strip()
    return (resp.status_code, len(body) // 256, urlparse(resp.url).path.replace(handle, ""))


_local = threading.local()


def session() -> requests.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        _local.s = s
    return s


def probe(c: dict) -> dict:
    """
    Ask one site about a real handle and an impossible one.

    Verdicts:
      DISCRIMINATES - the two answers differ. Usable.
      IDENTICAL     - the same answer for both. This is the site that would
                      report an account for every handle ever typed, and the
                      whole reason this harness exists.
      UNREACHABLE   - we could not get two clean answers. Says nothing about
                      the site; see the module docstring.
    """
    out = dict(c)
    try:
        s = session()
        a = s.get(c["url"].replace("{username}", c["claimed"]),
                  timeout=TIMEOUT, allow_redirects=True)
        # A beat between the pair, so the second request is not throttled
        # purely for following the first too closely.
        time.sleep(0.25 + random.random() * 0.4)
        b = s.get(c["url"].replace("{username}", c["unclaimed"]),
                  timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        out["verdict"] = "UNREACHABLE"
        out["why"] = type(e).__name__
        return out

    sa, sb = shape(a, c["claimed"]), shape(b, c["unclaimed"])
    out["claimed_status"], out["unclaimed_status"] = a.status_code, b.status_code

    # A pair of 429/5xx is the network refusing us, not the site answering.
    if a.status_code in (429, 500, 502, 503, 504) or b.status_code in (429, 500, 502, 503, 504):
        out["verdict"] = "UNREACHABLE"
        out["why"] = f"throttled {a.status_code}/{b.status_code}"
        return out

    # The same 401/403/406 for both handles is this machine being turned away
    # at the door, not the site failing to tell two handles apart. The first
    # sample run recorded 22 of 30 rejections this way, which would have
    # thrown out sites that answer a phone perfectly well -- the exact
    # datacentre-vs-mobile gap the app exists to exploit. Blocked is
    # unreachable; only a site that *answers* both and answers them the same
    # has actually failed the test.
    if a.status_code == b.status_code and a.status_code in (401, 403, 406, 451):
        out["verdict"] = "UNREACHABLE"
        out["why"] = f"blocked {a.status_code}"
        return out

    if sa == sb:
        out["verdict"] = "IDENTICAL"
        out["why"] = f"both {a.status_code}, same shape"
        return out

    out["verdict"] = "DISCRIMINATES"
    out["why"] = ("status" if a.status_code != b.status_code else "body")
    return out


def run(cands: list[dict], workers: int) -> list[dict]:
    done, results = 0, []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(probe, c): c for c in cands}
        for f in as_completed(futs):
            results.append(f.result())
            done += 1
            if done % 50 == 0 or done == len(cands):
                c = Counter(r["verdict"] for r in results)
                print(f"  {done}/{len(cands)}  "
                      f"discriminates={c['DISCRIMINATES']} identical={c['IDENTICAL']} "
                      f"unreachable={c['UNREACHABLE']}", flush=True)
    return results


# --------------------------------------------------------------------------
# emit
# --------------------------------------------------------------------------

CATEGORY = [
    ("Social", {"social", "us", "gb"}), ("Developer", {"coding", "tech", "it"}),
    ("Gaming", {"gaming", "games"}), ("Forum", {"forum", "discussion", "board"}),
    ("Media", {"video", "streaming", "music", "photo", "images"}),
    ("Knowledge", {"wiki", "education", "science", "news"}),
    ("Business", {"business", "finance", "shopping", "freelance"}),
]


def category_for(tags: list[str]) -> str:
    t = set(tags)
    for name, keys in CATEGORY:
        if t & keys:
            return name
    return "Other"


def kotlin(passed: list[dict]) -> str:
    """
    Emit the survivors as a third, separate tier.

    Deliberately its own file and its own object: the hand-built 559 are not
    touched, and deleting this file plus one `addAll` removes the experiment
    entirely.
    """
    rows = []
    for r in sorted(passed, key=lambda x: (category_for(x["tags"]), x["name"].lower())):
        name = r["name"].replace("\\", "").replace('"', "'")
        url = r["url"].replace('"', "'")
        rows.append(
            f'            p("{name}", "{url}", "{category_for(r["tags"])}"),'
            f'  // {r["why"]} {r["claimed_status"]}/{r["unclaimed_status"]}'
        )
    body = "\n".join(rows)
    return f'''package com.aryan.myrecon.data

/**
 * GENERATED -- do not edit by hand. Produced by tools/maigret_harness.py.
 *
 * Candidate platforms taken from the Maigret project's site list (MIT
 * licence, https://github.com/soxoj/maigret) and kept only where a live
 * differential probe showed the site answers a real handle and an impossible
 * one *differently*. Sites that answered both identically were discarded --
 * those are the ones that report an account for every handle ever typed.
 *
 * {len(passed)} of {{TOTAL}} candidates passed. The comment on each row is why it
 * passed and the two status codes it passed with.
 *
 * This tier is additive and removable: [PlatformCatalogue] is untouched, and
 * dropping this file plus its `addAll` in PlatformCatalogue.ALL reverts it.
 * These entries are NOT hand-verified to the standard of the other two tiers,
 * so they are gated behind the extended sweep rather than the default one.
 */
internal object PlatformCatalogueMaigret {{

    private fun p(name: String, url: String, category: String) = PlatformDef(
        name = name, template = url, okStatus = 200, category = category,
    )

    val ALL: List<PlatformDef> = buildList {{
        addAll(listOf(
{body}
        ))
    }}
}}
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="re-download data.json")
    ap.add_argument("--probe", action="store_true", help="run the live differential probe")
    ap.add_argument("--emit", action="store_true", help="write Kotlin for the survivors")
    ap.add_argument("--limit", type=int, default=0, help="probe only the first N candidates")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--all-langs", action="store_true", help="keep non-target-language sites")
    ap.add_argument("--root", default=os.path.dirname(HERE))
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    sites = fetch(a.fetch)
    hosts, names = existing(a.root)
    print(f"app catalogue: {len(hosts)} hosts / {len(names)} names")

    cands = candidates(sites, hosts, names, None if a.all_langs else KEEP_LANGS)
    print(f"maigret: {len(sites)} entries -> {len(cands)} candidates worth probing")
    json.dump(cands, open(os.path.join(OUT, "candidates.json"), "w", encoding="utf-8"), indent=1)

    if not a.probe:
        return

    if a.limit:
        random.seed(7)          # reproducible sample
        cands = random.sample(cands, min(a.limit, len(cands)))
        print(f"probing a random sample of {len(cands)}")

    t0 = time.time()
    results = run(cands, a.workers)
    print(f"probed {len(results)} in {time.time()-t0:.0f}s")

    json.dump(results, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"), indent=1)
    c = Counter(r["verdict"] for r in results)
    print("\n== verdicts ==")
    for k in ("DISCRIMINATES", "IDENTICAL", "UNREACHABLE"):
        print(f"  {k:14} {c[k]:5}  {c[k]/max(1,len(results)):6.1%}")

    passed = [r for r in results if r["verdict"] == "DISCRIMINATES"]
    print("\n== what the survivors are ==")
    for cat, n in Counter(category_for(r["tags"]) for r in passed).most_common():
        print(f"  {cat:12} {n}")
    print("\n== why sites were rejected ==")
    for why, n in Counter(r["why"] for r in results if r["verdict"] == "IDENTICAL").most_common(6):
        print(f"  {why:28} {n}")

    if a.emit and passed:
        src = kotlin(passed).replace("{TOTAL}", str(len(results)))
        dest = os.path.join(OUT, "PlatformCatalogueMaigret.kt")
        open(dest, "w", encoding="utf-8").write(src)
        print(f"\nwrote {dest}  ({len(passed)} platforms)")


if __name__ == "__main__":
    main()
