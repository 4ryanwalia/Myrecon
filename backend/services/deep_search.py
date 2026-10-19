"""Website Deep Search, mirroring the app's public sources and query plan."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.deep_search_plan import LABELS, build_plan, dedupe_key, is_profile, matches_context, section_for
from modules.deep_search_sources import ACTIVITY_SOURCES, NAME_SOURCES, Missing, keybase
from modules.deep_search_web import run_plan
from modules.profile_connections import connections


def _search_email(parsed, emit, stop):
    """Exact-email Google lookup only, with the public endpoint's projection."""
    from services.email_public_profiles import lookup_public_profiles

    subject = parsed["subject"]
    result = {"status": "pending", **parsed, "activity": [], "accounts": [], "people": [],
              "identity": None, "owner_links": [], "sections": [], "source_checks": [],
              "plan": [], "notes": [], "queries_run": 0, "partial": False,
              "google_public_profiles": {"query": {"email": subject}, "status": "pending",
                                         "profiles": [], "sources": []}}
    if stop.is_set():
        return result
    emit({"type": "progress", "phase": "Google public profile",
          "detail": "Resolving the exact email and checking public contributor reviews.", "percent": 5})
    emit({"type": "partial", "data": copy.deepcopy(result)})
    if stop.is_set():
        return result
    try:
        public = lookup_public_profiles(subject)
        if (not isinstance(public, dict) or not isinstance(public.get("profiles"), list)
                or not isinstance(public.get("sources"), list) or not isinstance(public.get("status"), str)):
            raise ValueError("Invalid public-profile result")
    except Exception:
        public = {"query": {"email": subject}, "status": "unavailable", "profiles": [],
                  "sources": [{"name": "Google public profile", "provider": "GHunt", "status": "unavailable",
                               "reason": "The public Google source could not complete this lookup."}]}
    result["google_public_profiles"] = public
    result["status"] = public["status"]
    result["partial"] = public["status"] not in ("ok", "no_match")
    result["source_checks"] = [{"source": source.get("name", "Google public source"),
                                "state": source.get("status", "unavailable")} for source in public["sources"]]
    result["notes"] = [
        "Only an exact-email public Google identity and its public contributor reviews are checked.",
        "Unavailable, private or incomplete review collections do not prove that no reviews exist.",
        "Profile edit dates describe profile changes and do not establish online or login activity.",
    ]
    if not stop.is_set():
        emit({"type": "progress", "phase": "Google public reviews",
              "detail": "Public Google lookup finished; source status and coverage are shown.", "percent": 98})
        emit({"type": "partial", "data": copy.deepcopy(result)})
    return result


def search(parsed, emit, stop=None):
    stop = stop or threading.Event()
    subject, mode, context = parsed["subject"], parsed["mode"], parsed["context"]
    if mode == "email":
        return _search_email(parsed, emit, stop)
    plan = build_plan(subject, mode, context)
    result = {"status": "ok", **parsed, "activity": [], "accounts": [], "people": [], "identity": None,
              "owner_links": [], "connections": [], "connection_trail": parsed.get("connection_trail", []),
              "connection_limits": {"suggestions": 30, "follow_depth": 3},
              "sections": [], "source_checks": [], "plan": plan, "notes": [], "queries_run": 0}
    lock = threading.Lock()
    seen = set()
    network_checks = {}

    def publish():
        if not stop.is_set():
            result["connections"] = connections(result, network_checks)
            emit({"type": "partial", "data": copy.deepcopy(result)})

    def web_hits(query, hits):
        with lock:
            for h in hits:
                if dedupe_key(h["url"]) in seen:
                    continue
                seen.add(dedupe_key(h["url"]))
                group = section_for(h["url"], query["section"])
                section = next((s for s in result["sections"] if s["section"] == group), None)
                if section is None:
                    section = {"section": group, "label": LABELS[group], "hits": []}
                    result["sections"].append(section)
                section["hits"].append({**h, "profile": mode == "handle" and is_profile(h["url"], subject),
                                        "matches_context": matches_context(h["title"] + " " + h["snippet"], context)})
            result["queries_run"] = sum(q["executed"] for q in plan)
            publish()

    def lookup(label, fn):
        try:
            return label, "checked", fn(subject)
        except Missing:
            return label, "not_found", None
        except Exception:
            return label, "unavailable", None

    sources = {**ACTIVITY_SOURCES, "Keybase": keybase} if mode == "handle" else NAME_SOURCES
    emit({"type": "progress", "phase": "Public sources", "detail": "Checking public records and indexed pages…", "percent": 2})
    # Request admission caps concurrent runs; this bounded pool caps each run.
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = {pool.submit(lookup, label, fn): label for label, fn in sources.items()}
        web = pool.submit(run_plan, plan, web_hits, stop)
        pending[web] = "Indexed web"
        completed = 0
        for future in as_completed(pending):
            if stop.is_set():
                continue
            with lock:
                if future is web:
                    try:
                        result["notes"].extend(future.result())
                    except Exception:
                        result["notes"].append("Indexed web search was unavailable. Use the browser query links to continue.")
                    result["queries_run"] = sum(q["executed"] for q in plan)
                else:
                    label, state, data = future.result()
                    result["source_checks"].append({"source": label, "state": state})
                    if data and label in ACTIVITY_SOURCES and mode == "handle":
                        result["activity"].append(data)
                        for link in data["declared"]:
                            result["owner_links"].append({**link, "declared_on": data["platform"] + " · " + data["handle"],
                                                          "source_url": data["url"]})
                    elif data:
                        result["accounts"].extend(data.get("accounts", []))
                        result["people"].extend(data.get("people", []))
                        if data.get("identity"):
                            result["identity"] = data["identity"]
                completed += 1
                emit({"type": "progress", "phase": "Checking sources", "detail": pending[future] + " completed", "percent": min(98, 2 + int(96 * completed / len(pending)))})
                publish()

    result["accounts"].sort(key=lambda a: not matches_context(a.get("detail", ""), context))
    result["people"].sort(key=lambda p: not matches_context(p.get("description", ""), context))
    for section in result["sections"]:
        section["hits"].sort(key=lambda h: (not h["profile"], not h["matches_context"]))
    result["sections"] = [s for s in result["sections"] if s["hits"]]
    result["partial"] = any(s["state"] == "unavailable" for s in result["source_checks"]) or bool(result["notes"]) or any(not a.get("activity_available", True) for a in result["activity"])
    result["notes"].extend([
        "Accounts sharing a handle can belong to unrelated people. Name records are candidates, not confirmed identities.",
        "Instagram results are indexed profiles, captions and mentions. Private content, likes and Instagram comment bodies are not available.",
        "Mastodon checks cover mastodon.social only. Public posts and comments are limited to the recent items each source returns.",
        "Linked handles are checked only when you choose Follow. Emails are never swept automatically. Suggestions and follow depth are bounded.",
    ])
    result["connections"] = connections(result, network_checks)
    return result
