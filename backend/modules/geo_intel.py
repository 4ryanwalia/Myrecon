"""
Geo intelligence — place identification from coordinates, using only free,
keyless services.

This is the honest substitute for "landmark recognition". Visual landmark
recognition needs a paid vision API; this module instead resolves the GPS
coordinates that many photos already carry, which — when they are present — is
*more* reliable than recognising a building from pixels. Big Ben resolves to
"Big Ben, Bridge Street, Westminster" from coordinates alone, with the Wikidata
id and the eight nearest notable places attached.

The trade is stated plainly in the output: `requires_gps` is always true. No GPS
means no result, and the module says so rather than guessing from image content.

Sources, all keyless and all with usage policies this module respects:
  • Nominatim (OpenStreetMap)  — reverse geocoding
  • Wikipedia REST + Action API — article summary and geosearch

Nominatim's policy requires a genuine identifying User-Agent and at most one
request per second from a single source. Both are enforced below. Exceeding it
gets an IP banned, which would take the feature down for every user, so the
throttle is not optional politeness.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKI_API = "https://en.wikipedia.org/w/api.php"

# Nominatim requires contact details in the agent string. A generic browser UA
# is a policy violation and gets blocked.
_UA = "MyRecon-OSINT/1.0 (https://myrecon.xyz; abuse@myrecon.xyz)"
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}
_TIMEOUT = 12

# One request per second, enforced across threads. Gunicorn runs 8 threads per
# worker, so a per-call sleep would not be enough on its own.
_MIN_INTERVAL = 1.05
_rate_lock = threading.Lock()
_last_call = 0.0


def _throttled_get(url: str, params: dict) -> Optional[dict]:
    """GET with the shared Nominatim rate limit applied. Returns None on any
    failure — geo enrichment is additive, so it must never break a scan."""
    global _last_call
    with _rate_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def _plain_get(url: str, params: Optional[dict] = None) -> Optional[dict]:
    """Wikipedia has no comparable rate limit for this volume, so it skips the
    Nominatim throttle and does not delay the request."""
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def _valid_coords(lat: Any, lon: Any) -> bool:
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    # Reject the null island exactly: 0,0 is overwhelmingly a zeroed GPS field
    # rather than a genuine position in the Gulf of Guinea.
    if la == 0 and lo == 0:
        return False
    return -90 <= la <= 90 and -180 <= lo <= 180


# ──────────────────────────────────────────────────────────────────────
#  Reverse geocoding
# ──────────────────────────────────────────────────────────────────────

def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Resolve coordinates to a named place and administrative hierarchy.

    Nominatim's `zoom` is left at its default so it returns the most specific
    named feature it has — which is what surfaces "Big Ben" rather than merely
    "Westminster".
    """
    out: dict[str, Any] = {"found": False, "source": "nominatim"}
    if not _valid_coords(lat, lon):
        out["error"] = "Coordinates are missing or invalid."
        return out

    data = _throttled_get(NOMINATIM_URL, {
        "lat": lat, "lon": lon, "format": "jsonv2",
        "addressdetails": 1, "extratags": 1,
    })
    if not data or "error" in data:
        out["error"] = "Reverse geocoding was unavailable."
        return out

    addr = data.get("address") or {}
    extra = data.get("extratags") or {}
    # Nominatim varies which key holds the settlement depending on country, so
    # fall through the plausible ones in decreasing specificity.
    settlement = (addr.get("city") or addr.get("town") or addr.get("village")
                  or addr.get("municipality") or addr.get("county"))

    out.update({
        "found": True,
        "name": data.get("name") or None,
        "display_name": data.get("display_name"),
        "category": data.get("category"),
        "type": data.get("type"),
        "address": {
            "road": addr.get("road"),
            "suburb": addr.get("suburb") or addr.get("neighbourhood"),
            "city": settlement,
            "state": addr.get("state"),
            "postcode": addr.get("postcode"),
            "country": addr.get("country"),
            "country_code": (addr.get("country_code") or "").upper() or None,
        },
        "wikidata": extra.get("wikidata"),
        "wikipedia": extra.get("wikipedia"),
        "osm": {
            "type": data.get("osm_type"),
            "id": data.get("osm_id"),
            "url": (f"https://www.openstreetmap.org/{data.get('osm_type')}/{data.get('osm_id')}"
                    if data.get("osm_type") and data.get("osm_id") else None),
        },
    })
    return out


# ──────────────────────────────────────────────────────────────────────
#  Wikipedia
# ──────────────────────────────────────────────────────────────────────

def nearby_places(lat: float, lon: float, radius_m: int = 1000, limit: int = 8) -> list[dict]:
    """Notable places within radius, nearest first. Radius is capped at
    Wikipedia's documented maximum of 10 km."""
    if not _valid_coords(lat, lon):
        return []
    data = _plain_get(WIKI_API, {
        "action": "query", "list": "geosearch",
        "gscoord": f"{lat}|{lon}",
        "gsradius": max(10, min(int(radius_m), 10000)),
        "gslimit": max(1, min(int(limit), 50)),
        "format": "json",
    })
    if not data:
        return []
    return [{
        "title": item.get("title"),
        "distance_m": round(item.get("dist", 0), 1),
        "lat": item.get("lat"),
        "lon": item.get("lon"),
        "url": "https://en.wikipedia.org/wiki/" + str(item.get("title", "")).replace(" ", "_"),
    } for item in (data.get("query") or {}).get("geosearch") or []]


def article_summary(title: str) -> Optional[dict]:
    """Lead extract and thumbnail for a Wikipedia article."""
    if not title:
        return None
    data = _plain_get(WIKI_REST + str(title).replace(" ", "_"))
    if not data or data.get("type") == "https://mediawiki.org/wiki/HyperSwitch/errors/not_found":
        return None
    return {
        "title": data.get("title"),
        "description": data.get("description"),
        "extract": data.get("extract"),
        "url": ((data.get("content_urls") or {}).get("desktop") or {}).get("page"),
        "thumbnail": (data.get("thumbnail") or {}).get("source"),
        "coordinates": data.get("coordinates"),
    }


# ──────────────────────────────────────────────────────────────────────
#  Orchestration
# ──────────────────────────────────────────────────────────────────────

def _confidence(place: dict, article: Optional[dict], nearest_m: Optional[float]) -> dict:
    """
    How firmly the coordinates identify a *named* place.

    The coordinates themselves are as accurate as the device that recorded
    them; what varies is whether they land on something identifiable. A named
    OSM feature with a matching Wikipedia article a few metres away is a
    confident identification. A bare road in open country is not.
    """
    factors: list[str] = []
    score = 0
    if place.get("found"):
        score += 30
        factors.append("coordinates resolved to an address")
    if place.get("name"):
        score += 25
        factors.append("coordinates fall on a named feature")
    if place.get("wikidata"):
        score += 20
        factors.append("feature has a Wikidata entity")
    if article:
        score += 15
        factors.append("matching Wikipedia article found")
    if nearest_m is not None and nearest_m <= 50:
        score += 10
        factors.append(f"notable place within {nearest_m:.0f} m")

    score = min(100, score)
    label = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return {"score": score, "band": label, "factors": factors}


def investigate_location(lat: float, lon: float, *, radius_m: int = 1000) -> dict:
    """
    Full location report for a coordinate pair.

    Intended to be fed straight from image_forensics' GPS block. Returns a
    `found: False` result rather than raising when there is nothing to report,
    so callers can include it unconditionally.
    """
    if not _valid_coords(lat, lon):
        return {
            "found": False,
            "requires_gps": True,
            "error": "No usable GPS coordinates.",
            "provenance": {"sources": [], "keyless": True},
        }

    place = reverse_geocode(lat, lon)
    nearby = nearby_places(lat, lon, radius_m=radius_m)

    # Prefer the article Nominatim points at; fall back to the closest notable
    # place, which is usually the same feature under its common name.
    article = None
    wiki_tag = place.get("wikipedia")
    if wiki_tag:
        # Format is "en:Article Title".
        article = article_summary(wiki_tag.split(":", 1)[-1])
    if not article and place.get("name"):
        article = article_summary(place["name"])
    if not article and nearby:
        article = article_summary(nearby[0]["title"])

    nearest = nearby[0]["distance_m"] if nearby else None

    return {
        "found": bool(place.get("found")),
        "requires_gps": True,
        "coordinates": {
            "latitude": round(float(lat), 6),
            "longitude": round(float(lon), 6),
            "maps": {
                "openstreetmap": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}",
            },
        },
        "place": place,
        "article": article,
        "nearby": nearby,
        "confidence": _confidence(place, article, nearest),
        "provenance": {
            "sources": [
                {"provider": "nominatim", "url": "https://nominatim.openstreetmap.org/",
                 "licence": "ODbL (OpenStreetMap contributors)", "keyless": True},
                {"provider": "wikipedia", "url": "https://en.wikipedia.org/",
                 "licence": "CC BY-SA", "keyless": True},
            ],
            "keyless": True,
            "note": "Derived from embedded GPS, not from image content. "
                    "No visual landmark recognition is performed.",
        },
    }
