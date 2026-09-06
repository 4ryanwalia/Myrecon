"""
Username / full-name search service.

Pipeline:
  1. Username enumeration across the platform database (verified matches only)
  2. Parallel profile enrichment (bio, followers, avatar) for the matches
  3. Optional Google dorking when a Custom Search key is configured, with
     every profile-shaped hit re-fetched and verified before it counts as a
     profile — search indexes lag reality, and a result the user clicks into
     a "no such account" page is worse than no result at all
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

from modules.username_checker import UsernameChecker, extract_metadata, verify_profile_url
from modules.google_dork import GoogleDorkEngine
from modules.correlator import IdentityCorrelator
from modules.enrichment import ProfileEnricher
from modules.code_exposure import github_commit_emails
from data.profile_urls import profile_handle
from utils.parser import categorise_result

_ENRICH_LIMIT = 18  # cap enrichment fan-out to keep latency predictable
_VERIFY_LIMIT = 24  # cap dork-hit verification fan-out for the same reason


def _has_google() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CX_ID"))


def _strip_binary(results: list[dict]) -> None:
    for r in results:
        r.pop("profile_pic_data", None)


def _noop(_event: dict) -> None:
    pass


def _enrich_profiles(found: list[dict], emit=_noop) -> None:
    """
    Enrich the strongest matches in parallel, emitting progress.

    Ranked before the cap is applied, not after. The list arrives in
    thread-completion order, so slicing it raw meant the avatar and bio a user
    actually came for could be dropped on a busy scan purely because Instagram
    answered nineteenth.
    """
    targets = sorted(
        (r for r in found if r.get("exists")), key=_profile_rank
    )[:_ENRICH_LIMIT]
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


def _verify_dork_profiles(results: list[dict], target: str, emit=_noop) -> None:
    """
    Re-fetch every profile-shaped dork hit and demote the ones that aren't real.

    A Custom Search hit only proves Google indexed that URL at some point.
    Profiles get deleted, renamed and suspended, and the shape check upstream
    cannot see any of that — so the survivors are fetched and scored with the
    same signals the platform sweep uses. Whatever fails becomes a mention: it
    stays visible as a lead, it just stops claiming to be an account.

    Anything past `_VERIFY_LIMIT` is demoted unchecked, because unverified and
    confirmed must not end up in the same bucket.
    """
    candidates = [r for r in results if r.get("category") == "profile"]
    if not candidates:
        return

    for r in candidates[_VERIFY_LIMIT:]:
        r["category"] = "mention"
    candidates = candidates[:_VERIFY_LIMIT]

    total = len(candidates)
    done = 0
    lock = threading.Lock()

    def _check(result: dict) -> None:
        nonlocal done
        url = result.get("url", "")
        try:
            verdict = verify_profile_url(url, target)
        except Exception:  # noqa: BLE001 - a failed check is a failed match
            verdict = {"ok": False, "status_code": -3, "meta": {}}

        if verdict["ok"]:
            result["exists"] = True
            result["verified"] = True
            result["confidence"] = verdict["confidence"]
            result["match_score"] = verdict["match_score"]
            result["status_code"] = verdict["status_code"]
            match = profile_handle(url)
            if match and not result.get("platform"):
                result["platform"] = match[0]
            extract_metadata(result, verdict["meta"])
        else:
            result["category"] = "mention"
            result["exists"] = False
            result["status_code"] = verdict["status_code"]

        with lock:
            done += 1
            emit({
                "type": "progress", "phase": "Searching the web",
                "percent": 95, "detail": f"Verifying web hits ({done}/{total})",
            })

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_check, candidates))


def _rejections(checker: UsernameChecker) -> list[dict]:
    """
    The platforms that were checked and deliberately not reported.

    Worth returning rather than discarding: "112 checked, none of them yours,
    here is what each one answered" is a stronger statement than silence, and
    it is the only way a user can tell a thorough scan from a lazy one. It is
    also the check on our own scoring — if a platform the user knows they are
    on shows up here, the reason says exactly which signal was missing.
    """
    out = []
    for r in getattr(checker, "all_results", []):
        if r.get("exists"):
            continue
        out.append({
            "platform": r.get("platform", ""),
            "url": r.get("url", ""),
            "status_code": r.get("status_code", 0),
            "reason": r.get("reason", ""),
        })
    out.sort(key=lambda r: r["platform"].lower())
    return out


def _code_exposure(profiles: list[dict], username: str, emit=_noop) -> list[dict]:
    """
    Findings about what the handle leaks, as opposed to where it exists.

    Only runs when GitHub was actually confirmed — it costs six API calls
    against a 60/hour unauthenticated budget, and spending those on a handle
    with no GitHub account would burn the allowance for six real scans.
    """
    on_github = any(
        r.get("exists") and "github.com/" in r.get("url", "").lower()
        and "gist." not in r.get("url", "").lower()
        for r in profiles
    )
    if not on_github:
        return []

    emit({"type": "progress", "phase": "Checking exposure", "percent": 96,
          "detail": "Reading public commit metadata…"})
    try:
        found = github_commit_emails(username)
    except Exception:  # noqa: BLE001 - an exposure check must not fail a scan
        return []

    if not (found.get("emails") or found.get("protected") or found.get("error")):
        return []
    return [{"type": "commit_email", "source": "github", **found}]


# Platforms surfaced first when they are found at all — the account a person
# actually came to look up, per category: Instagram and Pinterest for social,
# YouTube for video. The web UI shows every profile, but the Android app shows
# only the first account per category until the reward gate is unlocked, so the
# head of this list is the entire result for most people.
#
# Kept in step with PINNED in app/.../data/UsernameSweep.kt.
_PINNED_PLATFORMS = ("Instagram", "Pinterest", "YouTube")


def _profile_rank(result: dict) -> tuple:
    """
    Sort key: pinned platforms first, then confirmed before probable, then by
    name so the order is stable between scans.

    Without this, profiles came back in thread-completion order — whichever
    platform happened to answer first — so the same search could rank its
    results differently twice in a row.
    """
    platform = result.get("platform", "")
    try:
        pinned = _PINNED_PLATFORMS.index(platform)
    except ValueError:
        pinned = len(_PINNED_PLATFORMS)
    return (pinned, 0 if result.get("confidence") == "high" else 1, platform.lower())


def _bucket(results: list[dict]) -> tuple:
    """
    Split results into (profiles, documents, mentions).

    A profile must be confirmed — categorised as one *and* carrying `exists`.
    Anything shaped like a profile that was never confirmed is reported as a
    mention rather than quietly discarded, so the finding survives without
    overstating what is known about it.
    """
    profiles, documents, mentions = [], [], []
    for r in results:
        category = r.get("category")
        if category == "document":
            documents.append(r)
        elif category == "profile" and r.get("exists"):
            profiles.append(r)
        elif category == "profile":
            r["category"] = "mention"
            mentions.append(r)
        else:
            mentions.append(r)

    profiles.sort(key=_profile_rank)
    return profiles, documents, mentions


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

    rejected: list[dict] = []
    try:
        checker = UsernameChecker(max_workers=20 if deep else 12, delay=0)
        found = checker.scan(username, callback=_checker_cb, deep=deep)
        for r in found:
            r["category"] = categorise_result(r, username)
        all_results.extend(found)
        rejected = _rejections(checker)
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
                r["category"] = categorise_result(r, username)
            _verify_dork_profiles(dork_results, username, emit)
            all_results.extend(dork_results)
        except Exception:
            pass

    # ── Phase 4: what the handle leaks, not just where it exists ─
    exposures = _code_exposure(all_results, username, emit)

    # ── Phase 5: identity correlation ────────────────────────────
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

    profiles, documents, mentions = _bucket(all_results)

    return {
        "status": "ok",
        "query": {"username": username, "deep": deep},
        "summary": {
            "total": len(profiles) + len(documents) + len(mentions),
            "profiles": len(profiles),
            "documents": len(documents),
            "mentions": len(mentions),
            "clusters": len(clusters),
            "checked": len(profiles) + len(rejected),
            "rejected": len(rejected),
            "exposures": len(exposures),
        },
        "results": {"profiles": profiles, "documents": documents, "mentions": mentions},
        "identity_clusters": clusters,
        "exposures": exposures,
        "rejected": rejected,
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
        # No handle to match a full name against, so the URL shape is all the
        # cheap filtering there is; the HTTP verification below is what decides
        # whether a hit is a live profile.
        for r in dork_results:
            r["category"] = categorise_result(r)
        _verify_dork_profiles(dork_results, full_name)
        all_results.extend(dork_results)
    except Exception as e:  # noqa: BLE001
        all_results.append({
            "source": "google_dork", "error": True,
            "title": f"Dork error: {e}", "url": "",
        })

    _strip_binary(all_results)
    profiles, documents, mentions = _bucket(all_results)

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
