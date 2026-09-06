"""
Wayback Machine history — what was there before, and what is gone now.

The live checks answer one question: is this account there *today*. That
throws away two things worth knowing. An account that 404s now may have been
public for four years before somebody deleted it, which is a stronger finding
than the live check can produce. And a profile on a site that renders entirely
client-side scores nothing today, because the response carries no evidence
either way — but archive.org captured the same page when it was still
server-rendered, and that snapshot does carry evidence.

**This is deliberately a single-URL, on-demand lookup, not a scan phase.**
The CDX endpoint takes ~10s for a cold key and rate-limits aggressively —
fanning 20 profile URLs at it returns 429s and nothing else, while adding
twenty seconds to every scan. So the scan stays fast and the user asks for
archive history on the one result they care about. `rate_limited` comes back
as a distinct outcome rather than an empty result, because "archive.org told
us to slow down" and "this was never archived" mean opposite things.

Only 2xx/3xx captures count as proof the page existed: archive.org happily
snapshots a 404, and counting those would put us back to reporting accounts
that were never there.
"""

from urllib.parse import urlsplit

import requests

CDX_URL = "https://web.archive.org/cdx/search/cdx"
SNAPSHOT_URL = "https://web.archive.org/web/{timestamp}/{url}"

_HEADERS = {"User-Agent": "MyRecon/1.0 (+https://myrecon.xyz)"}
# Cold CDX keys routinely take 10s. Anything less just guarantees a timeout.
_TIMEOUT = 20
# One row per month: popular profiles have thousands of captures and we only
# need the shape of the timeline.
_COLLAPSE = "timestamp:6"
_LIMIT = 300


def _cdx_key(url: str) -> str:
    """
    CDX wants a bare host/path. Handing it a scheme-qualified URL turns a 10s
    lookup into a guaranteed timeout — it stops matching the index key and
    falls back to a scan.
    """
    parts = urlsplit(url)
    if not parts.netloc:
        return url.strip().lstrip("/")
    return f"{parts.netloc}{parts.path}".rstrip("/") or parts.netloc


def _month(timestamp: str) -> str:
    """20190315000000 -> 2019-03."""
    return f"{timestamp[:4]}-{timestamp[4:6]}" if len(timestamp) >= 6 else timestamp


def history(url: str, timeout: int = _TIMEOUT) -> dict:
    """
    Archive history for one URL.

    Returns ``{}`` when the page was never captured, ``{"rate_limited": True}``
    when archive.org is throttling us, and otherwise first/last month seen, the
    number of monthly captures, and a link to the most recent one.
    """
    if not url:
        return {}
    try:
        resp = requests.get(
            CDX_URL,
            params={
                "url": _cdx_key(url),
                "output": "json",
                "fl": "timestamp,statuscode",
                "collapse": _COLLAPSE,
                "limit": _LIMIT,
            },
            headers=_HEADERS,
            timeout=timeout,
        )
    except Exception:  # noqa: BLE001 - an unreachable archive is not a finding
        return {}

    if resp.status_code in (429, 503):
        return {"rate_limited": True}
    if resp.status_code != 200:
        return {}

    try:
        rows = resp.json()
    except ValueError:
        return {}
    if not isinstance(rows, list) or len(rows) < 2:
        return {}

    # rows[0] is the header row.
    live = sorted(
        ts for ts, status in (r[:2] for r in rows[1:])
        if str(status).startswith(("2", "3"))
    )
    if not live:
        return {}

    return {
        "first_seen": _month(live[0]),
        "last_seen": _month(live[-1]),
        "snapshots": len(live),
        "archive_url": SNAPSHOT_URL.format(timestamp=live[-1], url=url),
    }
