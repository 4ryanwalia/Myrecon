"""
Username / full-name search service.

Pipeline:
  1. Username enumeration across the platform database (verified matches only)
  2. Parallel profile enrichment (bio, followers, avatar) for the matches
  3. Optional Google dorking when a Custom Search key is configured
  4. Identity correlation into clusters

Two entry points share the same pipeline:
  * search_username(...)  -> runs it and returns the final dict (cached path)
  * stream_username(...)  -> a generator yielding progress events then the
    final result, for the live progress UI.
"""

import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from modules.username_checker import UsernameChecker
from modules.google_dork import GoogleDorkEngine
from modules.correlator import IdentityCorrelator
from modules.enrichment import ProfileEnricher
from utils.parser import categorise_result

_ENRICH_LIMIT = 18  # cap enrichment fan-out to keep latency predictable


def _has_google() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CX_ID"))


def _strip_binary(results: list[dict]) -> None:
    for r in results:
        r.pop("profile_pic_data", None)


def _noop(_event: dict) -> None:
    pass


def _enrich_profiles(found: list[dict], emit=_noop) -> None:
    """Enrich the strongest matches in parallel, emitting progress."""
    targets = [r for r in found if r.get("exists")][:_ENRICH_LIMIT]
    if not targets:
        return
    enricher = ProfileEnricher(delay=0)
    total = len(targets)
    done = 0
    lock = threading.Lock()

    def _run(result):
        nonlocal done
        try:
            enricher.enrich(result)
        except Exception:
            pass
        with lock:
            done += 1
            emit({
                "type": "progress", "phase": "Enriching profiles",
                "percent": 70 + int((done / total) * 25),
                "detail": f"Fetching avatars & bios ({done}/{total})",
            })

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_run, targets))


def _run_username(username: str, deep: bool, emit=_noop) -> dict:
    """Core username pipeline. `emit(event)` receives progress events."""
    all_results: list[dict] = []

    # ── Phase 1: verified username enumeration ───────────────────
    emit({"type": "progress", "phase": "Checking platforms", "percent": 2,
          "detail": "Starting scan…"})

    def _checker_cb(module, message, progress, results):
        emit({
            "type": "progress", "phase": "Checking platforms",
            "percent": max(2, int(progress * 0.68)), "detail": message,
        })

    try:
        checker = UsernameChecker(max_workers=20 if deep else 12, delay=0)
        found = checker.scan(username, callback=_checker_cb, deep=deep)
        for r in found:
            r["category"] = categorise_result(r)
        all_results.extend(found)
    except Exception as e:  # noqa: BLE001 - surface as a soft error
        all_results.append({
            "source": "username_check", "error": True, "platform": "Error",
            "url": "", "title": f"Username check error: {e}",
        })

    # ── Phase 2: enrichment (avatars, bios, follower counts) ─────
    emit({"type": "progress", "phase": "Enriching profiles", "percent": 70,
          "detail": "Fetching profile details…"})
    _enrich_profiles(all_results, emit)

    # ── Phase 3: Google dorking (optional) ───────────────────────
    if _has_google():
        emit({"type": "progress", "phase": "Searching the web", "percent": 95,
              "detail": "Google dorking…"})
        try:
            dork = GoogleDorkEngine(delay=0.2)
            dork_results = dork.scan_username(username, deep=deep)
            for r in dork_results:
                r["category"] = categorise_result(r)
            all_results.extend(dork_results)
        except Exception:
            pass

    # ── Phase 4: identity correlation ────────────────────────────
    emit({"type": "progress", "phase": "Correlating identities", "percent": 97,
          "detail": "Linking profiles across platforms…"})
    clusters = []
    try:
        clusters = IdentityCorrelator().correlate(all_results, target_username=username)
        for c in clusters:
            c.pop("profile_pic_data", None)
    except Exception:
        pass

    _strip_binary(all_results)

    profiles = [r for r in all_results if r.get("category") == "profile" and r.get("exists")]
    documents = [r for r in all_results if r.get("category") == "document"]
    mentions = [r for r in all_results if r.get("category") == "mention"]

    return {
        "status": "ok",
        "query": {"username": username, "deep": deep},
        "summary": {
            "total": len(profiles) + len(documents) + len(mentions),
            "profiles": len(profiles),
            "documents": len(documents),
            "mentions": len(mentions),
            "clusters": len(clusters),
        },
        "results": {"profiles": profiles, "documents": documents, "mentions": mentions},
        "identity_clusters": clusters,
    }


def search_username(username: str, deep: bool = False) -> dict:
    """Non-streaming entry point (used by the cached JSON endpoint)."""
    return _run_username(username, deep, _noop)


def stream_username(username: str, deep: bool = False):
    """
    Generator yielding progress event dicts, ending with either
    {"type": "complete", "data": <result>} or {"type": "error", ...}.

    The pipeline runs on a worker thread and pushes events through a queue
    so they can be streamed to the client as they happen.
    """
    q: "queue.Queue" = queue.Queue()
    holder: dict = {}

    def emit(event: dict) -> None:
        q.put(event)

    def worker():
        try:
            holder["data"] = _run_username(username, deep, emit)
        except Exception as e:  # noqa: BLE001
            holder["error"] = str(e)
        finally:
            q.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    while True:
        event = q.get()
        if event is None:
            break
        yield event

    if "error" in holder:
        yield {"type": "error", "error": holder["error"]}
    else:
        yield {"type": "complete", "data": holder["data"]}


def search_fullname(full_name: str, deep: bool = False) -> dict:
    all_results: list[dict] = []

    if not _has_google():
        return {
            "status": "ok",
            "query": {"full_name": full_name, "deep": deep},
            "summary": {"total": 0, "profiles": 0, "documents": 0, "mentions": 0},
            "results": {"profiles": [], "documents": [], "mentions": []},
            "notice": "Full-name search requires a Google Custom Search key on the server.",
        }

    try:
        dork = GoogleDorkEngine(delay=0.2)
        dork_results = dork.scan_username(full_name, deep=deep)
        for r in dork_results:
            r["category"] = categorise_result(r)
        all_results.extend(dork_results)
    except Exception as e:  # noqa: BLE001
        all_results.append({
            "source": "google_dork", "error": True,
            "title": f"Dork error: {e}", "url": "",
        })

    _strip_binary(all_results)
    profiles = [r for r in all_results if r.get("category") == "profile"]
    documents = [r for r in all_results if r.get("category") == "document"]
    mentions = [r for r in all_results if r.get("category") == "mention"]

    return {
        "status": "ok",
        "query": {"full_name": full_name, "deep": deep},
        "summary": {
            "total": len(all_results),
            "profiles": len(profiles),
            "documents": len(documents),
            "mentions": len(mentions),
        },
        "results": {"profiles": profiles, "documents": documents, "mentions": mentions},
    }
