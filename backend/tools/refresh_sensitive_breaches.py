"""Rebuild data/sensitive-breaches.json from the two free breach catalogues.

Run from backend/:  python tools/refresh_sensitive_breaches.py

Have I Been Pwned (IsSensitive) and XposedOrNot (sensitive) flag breaches
where merely appearing reveals something private: adult and dating sites,
political correspondence, health services, stalkerware. The email tool lets
anyone type any address, so modules/sensitive_breaches.py drops these from
every result, the way HIBP's own public search does. Both catalogues are
keyless and contain no personal data. The snapshot is committed so the
filter never depends on a third party answering at scan time.
"""
import json
import os
import sys
from datetime import date

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from modules.sensitive_breaches import key  # noqa: E402  same normaliser as the filter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "sensitive-breaches.json")
HEADERS = {"User-Agent": "MyRecon-SensitiveList/1.0 (+https://www.myrecon.xyz)", "Accept": "application/json"}


def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    names, domains = set(), set()
    hibp = fetch("https://haveibeenpwned.com/api/v3/breaches")
    hibp_count = 0
    for b in hibp:
        if b.get("IsSensitive") is True:
            hibp_count += 1
            names.update(filter(None, (b.get("Name"), b.get("Title"))))
            if b.get("Domain"):
                domains.add(b["Domain"].lower())
    xon = fetch("https://api.xposedornot.com/v1/breaches").get("exposedBreaches") or []
    xon_count = 0
    for b in xon:
        if b.get("sensitive") is True:
            xon_count += 1
            if b.get("breachID"):
                names.add(b["breachID"])
            if b.get("domain"):
                domains.add(b["domain"].lower())
    # A domain is only a safe match key when every catalogue entry using it is
    # sensitive. 163.com, for example, carries a sensitive entry and ordinary
    # ones; matching on it would hide the ordinary breaches too.
    shared = {b["Domain"].lower() for b in hibp if b.get("Domain") and b.get("IsSensitive") is not True}
    shared |= {b["domain"].lower() for b in xon if b.get("domain") and b.get("sensitive") is not True}
    dropped = sorted(domains & shared)
    domains -= shared
    if dropped:
        print("domains shared with non-sensitive breaches, matched by name only:", ", ".join(dropped))
    ordinary = {key(n) for b in hibp if b.get("IsSensitive") is not True for n in (b.get("Name"), b.get("Title")) if n}
    ordinary |= {key(b["breachID"]) for b in xon if b.get("breachID") and b.get("sensitive") is not True}
    clashing = sorted(n for n in names if key(n) in ordinary)
    names -= set(clashing)
    if clashing:
        print("names shared with non-sensitive breaches, left out:", ", ".join(clashing))
    if hibp_count < 20 or xon_count < 20:
        sys.exit(f"Refusing to write a suspiciously short list (HIBP {hibp_count}, XON {xon_count}).")
    payload = {
        "generated": date.today().isoformat(),
        "sources": {"haveibeenpwned": hibp_count, "xposedornot": xon_count},
        "names": sorted(names, key=str.lower),
        "domains": sorted(domains),
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"wrote {len(names)} names and {len(domains)} domains "
          f"(HIBP {hibp_count} sensitive, XposedOrNot {xon_count} sensitive)")


if __name__ == "__main__":
    main()
