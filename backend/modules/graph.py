"""
Investigation graph — entities, relationships, confidence and provenance.

This is the correlation core. Feeds (username scan, email scan, domain scan,
image forensics, …) each emit entities and edges through an adapter; the graph
merges them, scores confidence, and derives clusters and a timeline.

Three rules hold throughout, because an investigation tool that breaks them is
worse than no tool:

  1. Every entity and every edge carries provenance. If a field cannot say
     where it came from, it does not go in the graph.
  2. Confidence is computed from named factors, never asserted. The factor
     list travels with the score so a reader can audit it.
  3. Identity is never inferred from appearance. Faces are geometry; a face
     does not produce a Person node. Merging requires a shared *identifier* —
     a username, an email, a domain, a key fingerprint.

No third-party services and no API keys: this module is pure logic over data
the caller already has, so it is fully deterministic and unit-testable.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Optional

# ──────────────────────────────────────────────────────────────────────
#  Vocabulary
# ──────────────────────────────────────────────────────────────────────

# Entity types. Kept open-ended deliberately — a new feed may introduce a type
# without a schema migration — but these are the ones the UI styles.
class EntityType:
    PERSON = "person"
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    DOMAIN = "domain"
    WEBSITE = "website"
    IP = "ip"
    ORGANISATION = "organisation"
    LOCATION = "location"
    IMAGE = "image"
    DEVICE = "device"
    SOCIAL_PROFILE = "social_profile"
    BREACH = "breach"
    JOB_TITLE = "job_title"
    SCHOOL = "school"


class EdgeType:
    USES = "uses"                    # person/identity -> username, email
    OWNS = "owns"                    # entity -> domain, website
    REGISTERED = "registered"        # entity -> domain (from WHOIS/RDAP)
    APPEARS_ON = "appears_on"        # username -> social profile / page
    SAME_USERNAME = "same_username"
    SAME_EMAIL = "same_email"
    SAME_DOMAIN = "same_domain"
    SAME_PHOTO = "same_photo"        # perceptual-hash match between images
    MENTIONS = "mentions"
    RESOLVES_TO = "resolves_to"      # domain -> ip
    HOSTS = "hosts"                  # ip -> domain
    LOCATED_IN = "located_in"
    EXPOSED_IN = "exposed_in"        # email -> breach
    CAPTURED_BY = "captured_by"      # image -> device
    WORKS_AT = "works_at"
    MEMBER_OF = "member_of"


# Confidence bands. The numeric score is what the engine computes; the label is
# for display only, and the thresholds live in one place so they stay coherent.
CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_LOW = "low"

_HIGH_AT = 70
_MEDIUM_AT = 40


def band(score: int) -> str:
    if score >= _HIGH_AT:
        return CONF_HIGH
    if score >= _MEDIUM_AT:
        return CONF_MEDIUM
    return CONF_LOW


# Correlation factor weights. These are heuristics, and saying so in the code
# matters: a shared email is near-conclusive, a shared city is barely evidence.
FACTOR_WEIGHTS: dict[str, int] = {
    "same_email": 45,          # an email address is effectively an identifier
    "same_domain_owner": 35,   # WHOIS/RDAP registrant match
    "same_username_verified": 30,   # identical handle, confirmed to exist
    "same_photo_hash": 30,     # perceptual hash within threshold
    "same_phone": 30,
    "same_username_unverified": 12,  # identical handle, existence not confirmed
    "same_employer": 15,
    "linked_from_profile": 20,  # profile A explicitly links profile B
    "multiple_sources": 15,     # corroborated by independent feeds
    "same_city": 5,             # weak on its own; common cities are meaningless
    "same_display_name": 8,
}


# ──────────────────────────────────────────────────────────────────────
#  Normalisation
# ──────────────────────────────────────────────────────────────────────

_WS = re.compile(r"\s+")


def normalise(entity_type: str, value: str) -> str:
    """
    Canonical form used for identity and de-duplication.

    Two feeds that disagree on case or on a www. prefix must still land on one
    node, so normalisation is what makes merging work at all. It is applied to
    the identity key only — the human-facing label keeps the original text.
    """
    v = _WS.sub(" ", str(value or "")).strip()
    if not v:
        return ""

    if entity_type in (EntityType.EMAIL, EntityType.DOMAIN, EntityType.WEBSITE,
                       EntityType.USERNAME, EntityType.IP):
        v = v.lower()

    if entity_type == EntityType.EMAIL:
        # Gmail ignores dots and everything after '+'. Folding them prevents
        # one mailbox appearing as several people.
        local, _, domain = v.partition("@")
        if domain in ("gmail.com", "googlemail.com"):
            local = local.split("+")[0].replace(".", "")
            v = f"{local}@gmail.com"
        else:
            local = local.split("+")[0]
            v = f"{local}@{domain}" if domain else local

    if entity_type in (EntityType.DOMAIN, EntityType.WEBSITE):
        v = re.sub(r"^https?://", "", v)
        v = re.sub(r"^www\.", "", v)
        v = v.split("/")[0].rstrip(".")

    if entity_type == EntityType.USERNAME:
        v = v.lstrip("@")

    return v


def entity_id(entity_type: str, value: str) -> str:
    """
    Stable content-addressed id.

    Deriving the id from (type, normalised value) rather than a counter means
    the same entity discovered by two feeds, or across two runs, collides on
    one id automatically. Merging becomes a dict write instead of a matching
    pass.
    """
    key = f"{entity_type}:{normalise(entity_type, value)}"
    return f"{entity_type[:2]}_{hashlib.sha1(key.encode()).hexdigest()[:12]}"


# ──────────────────────────────────────────────────────────────────────
#  Graph
# ──────────────────────────────────────────────────────────────────────

class InvestigationGraph:
    """
    Accumulates entities and edges from any number of feeds.

    Not thread-safe by design: one graph belongs to one investigation on one
    request, matching the backend's synchronous, serverless-safe style.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}
        self._edges: dict[str, dict] = {}

    # ---- ingest ----------------------------------------------------

    def add_entity(
        self,
        entity_type: str,
        value: str,
        *,
        label: Optional[str] = None,
        source: Optional[dict] = None,
        factors: Optional[Iterable[str]] = None,
        attrs: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Add or merge an entity. Returns its id, or None if the value was empty.

        Repeated calls for the same entity accumulate sources, factors and
        attributes rather than overwriting — that accumulation is precisely
        what drives the confidence score up.
        """
        norm = normalise(entity_type, value)
        if not norm:
            return None

        nid = entity_id(entity_type, value)
        node = self._nodes.get(nid)
        if node is None:
            node = self._nodes[nid] = {
                "id": nid,
                "type": entity_type,
                "value": norm,
                "label": (label or str(value)).strip(),
                "sources": [],
                "factors": [],
                "attrs": {},
            }

        if source:
            # Same provider+url twice is one source, not corroboration.
            key = (source.get("provider"), source.get("url"))
            if key not in {(s.get("provider"), s.get("url")) for s in node["sources"]}:
                node["sources"].append(source)

        for f in factors or ():
            if f not in node["factors"]:
                node["factors"].append(f)

        for k, v in (attrs or {}).items():
            # First non-empty value wins; later feeds do not clobber it. Keeps
            # the richest early answer instead of the last one to arrive.
            if v not in (None, "", [], {}) and node["attrs"].get(k) in (None, "", [], {}):
                node["attrs"][k] = v

        return nid

    def add_edge(
        self,
        source_id: Optional[str],
        target_id: Optional[str],
        edge_type: str,
        *,
        source: Optional[dict] = None,
        factors: Optional[Iterable[str]] = None,
        at: Optional[str] = None,
    ) -> Optional[str]:
        """Relate two entities. Silently ignored if either endpoint is missing,
        so callers can pass add_entity() results straight through."""
        if not source_id or not target_id or source_id == target_id:
            return None
        if source_id not in self._nodes or target_id not in self._nodes:
            return None

        eid = f"e_{hashlib.sha1(f'{source_id}|{edge_type}|{target_id}'.encode()).hexdigest()[:12]}"
        edge = self._edges.get(eid)
        if edge is None:
            edge = self._edges[eid] = {
                "id": eid, "source": source_id, "target": target_id,
                "type": edge_type, "sources": [], "factors": [], "at": at,
            }
        if source:
            key = (source.get("provider"), source.get("url"))
            if key not in {(s.get("provider"), s.get("url")) for s in edge["sources"]}:
                edge["sources"].append(source)
        for f in factors or ():
            if f not in edge["factors"]:
                edge["factors"].append(f)
        if at and not edge["at"]:
            edge["at"] = at
        return eid

    # ---- confidence ------------------------------------------------

    @staticmethod
    def score(factors: Iterable[str], source_count: int) -> dict:
        """
        Combine correlation factors into a 0–100 score with its reasoning.

        Diminishing returns rather than a plain sum: ten weak signals must not
        add up to certainty. Each successive factor contributes less, so the
        score is dominated by the strongest evidence present.
        """
        weighted = sorted(
            ((f, FACTOR_WEIGHTS.get(f, 5)) for f in dict.fromkeys(factors)),
            key=lambda kv: kv[1], reverse=True,
        )
        total = 0.0
        for i, (_, w) in enumerate(weighted):
            total += w * (0.6 ** i)

        # Independent corroboration is itself evidence, capped so that volume
        # alone cannot manufacture a high score.
        if source_count > 1:
            total += min(FACTOR_WEIGHTS["multiple_sources"], 5 * (source_count - 1))

        s = int(max(0, min(100, round(total))))
        return {
            "score": s,
            "band": band(s),
            "factors": [{"name": f, "weight": w} for f, w in weighted],
            "source_count": source_count,
        }

    # ---- output ----------------------------------------------------

    def clusters(self) -> list[dict]:
        """
        Connected components over the graph — each is a candidate identity.

        A component is a *hypothesis*, not a person. It is labelled with its
        strongest-confidence member and reports its own aggregate confidence so
        a weak cluster reads as weak.
        """
        parent: dict[str, str] = {n: n for n in self._nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for e in self._edges.values():
            a, b = find(e["source"]), find(e["target"])
            if a != b:
                parent[a] = b

        groups: dict[str, list[str]] = {}
        for n in self._nodes:
            groups.setdefault(find(n), []).append(n)

        out = []
        for root, members in groups.items():
            if len(members) < 2:
                continue  # a lone node is not a correlation
            nodes = [self._nodes[m] for m in members]
            all_factors = [f for n in nodes for f in n["factors"]]
            srcs = {(s.get("provider"), s.get("url")) for n in nodes for s in n["sources"]}
            conf = self.score(all_factors, len(srcs))
            # Label from the highest-confidence identifier-bearing member.
            ranked = sorted(
                nodes,
                key=lambda n: self.score(n["factors"], len(n["sources"]))["score"],
                reverse=True,
            )
            out.append({
                "id": f"c_{root}",
                "size": len(members),
                "label": ranked[0]["label"],
                "members": members,
                "types": sorted({n["type"] for n in nodes}),
                "confidence": conf,
            })
        return sorted(out, key=lambda c: (-c["confidence"]["score"], -c["size"]))

    def timeline(self) -> list[dict]:
        """
        Dated events, oldest first.

        Only entities and edges that actually carry a date appear. Nothing is
        interpolated or guessed — a sparse timeline is the honest output when
        the sources are sparse.
        """
        events: list[dict] = []
        for n in self._nodes.values():
            when = n["attrs"].get("created_at") or n["attrs"].get("date")
            if when:
                events.append({
                    "at": str(when), "kind": n["type"], "entity": n["id"],
                    "label": n["label"],
                    "detail": n["attrs"].get("event_detail") or f"{n['type']} recorded",
                    "sources": n["sources"],
                })
        for e in self._edges.values():
            if e.get("at"):
                events.append({
                    "at": str(e["at"]), "kind": e["type"], "entity": e["source"],
                    "label": self._nodes[e["source"]]["label"],
                    "detail": f"{e['type'].replace('_', ' ')} "
                              f"{self._nodes[e['target']]['label']}",
                    "sources": e["sources"],
                })
        # Lexicographic sort is correct for ISO-8601 and for bare years, which
        # is all the feeds produce.
        return sorted(events, key=lambda x: x["at"])

    def to_dict(self) -> dict:
        """Serialise the whole graph with confidence resolved on every element."""
        nodes = []
        for n in self._nodes.values():
            nodes.append({**n, "confidence": self.score(n["factors"], len(n["sources"]))})
        edges = []
        for e in self._edges.values():
            edges.append({**e, "confidence": self.score(e["factors"], len(e["sources"]))})

        clusters = self.clusters()
        return {
            "nodes": sorted(nodes, key=lambda n: -n["confidence"]["score"]),
            "edges": edges,
            "clusters": clusters,
            "timeline": self.timeline(),
            "summary": {
                "entities": len(nodes),
                "relationships": len(edges),
                "clusters": len(clusters),
                "by_type": {
                    t: sum(1 for n in nodes if n["type"] == t)
                    for t in sorted({n["type"] for n in nodes})
                },
                "strongest_cluster": clusters[0]["confidence"] if clusters else None,
            },
        }
