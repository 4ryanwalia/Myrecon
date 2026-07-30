"""
Investigation orchestrator — a handle in, a correlated graph out.

    handle ─▶ username sweep (100+ platforms)
                  │
                  ▼
              graph adapter ─▶ entities, edges, clusters, timeline
                  │
                  ▼
              rule-based assessment

Search by *name* was built and then removed. Deriving handles from a personal
name ("A. Likhiya" → `alikhiya`, `ashmi.likhiya`) produced accounts belonging to
whoever actually registered those handles, which is usually not the person
searched. The inference "this naming convention implies this person" is not
supported by anything, so the findings were false positives by construction —
not a scoring problem that better weights could fix. A handle, by contrast, is
an identifier: searching `torvalds` finds accounts named `torvalds`, which is a
fact rather than a guess.

Two things this still deliberately does not do:

  • Assert identity. Sharing a handle across platforms is evidence, not proof,
    and the assessment says so. A cluster is a hypothesis with a confidence
    band attached.
  • Invent narrative. The assessment is generated from the graph's own counts
    and confidence values — no language model — so the prose cannot claim
    anything the evidence does not support.

Synchronous and stateless, matching the rest of the backend.
"""

from __future__ import annotations

from typing import Callable, Optional

from modules.graph import EdgeType as EK
from modules.graph import EntityType as ET
from modules.graph import InvestigationGraph
# _run_username is the core pipeline with a progress callback; search_username
# is that with the callback discarded. Calling the core directly is what lets
# per-platform progress reach the client instead of one silent block.
from services.search import _run_username

# Platforms whose presence meaningfully corroborates an identity, because they
# expose a verifiable link (a signed proof, a commit email, a DNS record)
# rather than only a display name.
_CORROBORATING = {"github", "keybase", "gitlab", "stackoverflow"}


def _noop(_: dict) -> None:
    pass


def _platform_of(result: dict) -> str:
    return str(result.get("platform") or result.get("display_link") or "").strip()


def ingest_username_scan(graph: InvestigationGraph, scan: dict) -> Optional[str]:
    """
    Fold a username scan into the graph.

    The handle becomes the hub and each confirmed profile hangs off it. Returns
    the hub's node id.
    """
    handle = (scan.get("query") or {}).get("username", "")
    if not handle:
        return None

    hub = graph.add_entity(
        ET.USERNAME, handle,
        source={"provider": "username_scan", "url": None},
        factors=["same_username_verified"],
    )

    for p in (scan.get("results") or {}).get("profiles") or []:
        platform = _platform_of(p)
        url = p.get("url")
        if not platform or not url:
            continue

        src = {"provider": platform, "url": url}
        pf = ["same_username_verified"] if p.get("exists") else ["same_username_unverified"]
        if platform.lower() in _CORROBORATING:
            pf.append("multiple_sources")

        node = graph.add_entity(
            ET.SOCIAL_PROFILE, url,
            label=f"{platform}/{handle}",
            source=src, factors=pf,
            attrs={
                "platform": platform,
                "url": url,
                "avatar": p.get("profile_pic_url") or p.get("avatar_url"),
                "bio": p.get("bio"),
                "title": p.get("title"),
                "scan_confidence": p.get("confidence"),
            },
        )
        graph.add_edge(hub, node, EK.APPEARS_ON, source=src, factors=pf)

    # Clusters the correlator already found are corroboration between existing
    # profiles, not new entities.
    for cluster in scan.get("identity_clusters") or []:
        members = cluster.get("profiles") or cluster.get("members") or []
        urls = [m.get("url") for m in members if isinstance(m, dict) and m.get("url")]
        for i in range(len(urls) - 1):
            a = graph.add_entity(ET.SOCIAL_PROFILE, urls[i])
            b = graph.add_entity(ET.SOCIAL_PROFILE, urls[i + 1])
            graph.add_edge(a, b, EK.SAME_USERNAME,
                           source={"provider": "correlator", "url": None},
                           factors=["multiple_sources"])

    return hub


def assess(graph_dict: dict, *, handle: str) -> dict:
    """
    Rule-based narrative over the graph.

    Every sentence derives from a count or confidence value present in the
    report, so the prose cannot drift from the evidence.
    """
    summary = graph_dict["summary"]
    clusters = graph_dict["clusters"]
    profiles = summary["by_type"].get(ET.SOCIAL_PROFILE, 0)
    strongest = clusters[0] if clusters else None
    score = strongest["confidence"]["score"] if strongest else 0
    band = strongest["confidence"]["band"] if strongest else "low"

    lines = [f'The handle "{handle}" was checked across public platforms.']

    if not profiles:
        lines.append("No public accounts were found using this handle.")
    else:
        lines.append(
            f"{profiles} public account{'s were' if profiles != 1 else ' was'} found."
        )

    if strongest and strongest["size"] > 1:
        factors = ", ".join(f["name"].replace("_", " ")
                            for f in strongest["confidence"]["factors"][:3])
        lines.append(
            f"They cluster at {score}/100 ({band} confidence), on: {factors}."
        )

    if profiles:
        lines.append(
            "Accounts sharing a handle are frequently unrelated people. This is a "
            "set of accounts using the same name, not a confirmed single identity."
        )

    return {
        "text": " ".join(lines),
        "confidence": {"score": score, "band": band},
        "generated_by": "rule-based (no language model)",
        "notes": [],
    }


def investigate(handle: str, *, deep: bool = False,
                emit: Optional[Callable[[dict], None]] = None) -> dict:
    """
    Run an investigation on a single handle.

    Args:
        handle: the username to check. Must be an actual handle — names are not
            accepted, see the module docstring.
        deep: passed through to the platform sweep.
        emit: optional progress callback, matching the event shape the username
            stream already uses so the frontend reuses one renderer.
    """
    emit = emit or _noop
    handle = (handle or "").strip().lstrip("@")
    if not handle:
        return {"status": "error", "error": "Enter a handle to investigate."}

    graph = InvestigationGraph()
    notes: list[str] = []

    emit({"type": "progress", "phase": f"Scanning {handle}", "percent": 2,
          "detail": f"Checking platforms for {handle}…"})

    # Rescale the sweep's 0-100 into 2-92 so the client's bar advances smoothly
    # and leaves room for the correlation step.
    def relay(ev: dict) -> None:
        emit({**ev,
              "phase": f"Scanning {handle}",
              "percent": int(2 + 90 * (ev.get("percent", 0) / 100))})

    try:
        scan = _run_username(handle, deep, relay)
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return {"status": "error", "error": f"Scan failed: {exc}"}

    ingest_username_scan(graph, scan)

    emit({"type": "progress", "phase": "Correlating", "percent": 95,
          "detail": "Building the relationship graph…"})

    g = graph.to_dict()
    return {
        "status": "ok",
        "query": {"value": handle, "deep": deep},
        "handle": handle,
        "graph": g,
        "assessment": assess(g, handle=handle),
        "scans": [{"handle": handle,
                   "profiles": (scan.get("summary") or {}).get("profiles", 0)}],
        "notes": notes,
    }
