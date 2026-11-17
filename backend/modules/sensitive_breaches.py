"""Keep sensitive breaches out of email results.

Anyone can type any address into the email tool. For most breaches that only
tells a stranger what a breach search engine would. For breaches that Have I
Been Pwned or XposedOrNot flag as sensitive (adult and dating sites, political
correspondence, health services, stalkerware) appearing at all reveals
something private, so HIBP shows them only to a verified owner of the address.
This module applies the same rule: such breaches are dropped from every source
before anything is counted, listed or linked.

The list lives in data/sensitive-breaches.json, rebuilt by
tools/refresh_sensitive_breaches.py. A match is by breach name, or by domain
when that domain is used only by sensitive breaches. When in doubt the rule
errs towards hiding: a hidden ordinary breach costs completeness, a shown
sensitive one cannot be taken back.
"""
import json
import os
import re
from functools import lru_cache

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sensitive-breaches.json")
_TLD = re.compile(r"\.(com|net|org|io|co|me|ru|de|fr|uk|in|nl|xyz|cc|ai|au|hu)$")

# LeakCheck names many breaches neither catalogue knows (for example
# "Sexclub.ru"), so names that plainly describe adult or dating services are
# treated as sensitive too. The lookbehinds keep Essex, Sussex and Middlesex
# out; a hidden ordinary breach is the acceptable failure here.
_ADULT = re.compile(
    r"porn|xxx|(?<!es)(?<!us)(?<!le)sex|escort|hookup|nude|fetish|erotic|swinger|"
    r"camgirl|webcam.?model|onlyfans|hentai|milf|(?<![a-z])dating|(?-i:(?<=[a-z])Dating)|"
    r"adultfriend|adult.?(site|chat|dating|club|video)|stripchat|brazzers",
    re.I,
)

# Shown with every email result, whatever was found. It must not vary with
# the result, or its presence would itself reveal a sensitive match.
POLICY_NOTE = ("Breaches flagged as sensitive, such as adult or dating sites, are never shown here, "
               "because anyone can type an address. To see them for your own address, use "
               "Have I Been Pwned's notification service, which verifies that you own it.")


def key(value) -> str:
    """Breach names, titles and domains reduced to one comparable form."""
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://", "", text).split("/")[0]
    text = re.sub(r"^www\.", "", text)
    text = _TLD.sub("", text)
    return re.sub(r"[^a-z0-9]", "", text)


@lru_cache(maxsize=1)
def _keys():
    with open(_DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    names = {key(n) for n in data.get("names", [])}
    domains = {key(d) for d in data.get("domains", [])}
    names.discard("")
    domains.discard("")
    return frozenset(names), frozenset(domains)


def is_sensitive(name="", domain="") -> bool:
    if _ADULT.search(str(name or "")) or _ADULT.search(str(domain or "")):
        return True
    names, domains = _keys()
    name_key = key(name)
    if name_key and (name_key in names or name_key in domains):
        return True
    domain_key = key(domain)
    return bool(domain_key and domain_key in domains)


def drop_sensitive(rows, name_field="name", domain_field="domain"):
    """Return (kept rows, number dropped). Rows that are not dicts are kept as is."""
    kept, dropped = [], 0
    for row in rows or []:
        if isinstance(row, dict) and is_sensitive(row.get(name_field, ""), row.get(domain_field, "")):
            dropped += 1
            continue
        kept.append(row)
    return kept, dropped
