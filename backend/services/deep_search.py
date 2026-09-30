"""Website Deep Search, mirroring the app's public sources and query plan."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, urlsplit

from modules.deep_search_plan import LABELS, build_plan, dedupe_key, is_profile, matches_context, section_for
from modules.deep_search_sources import ACTIVITY_SOURCES, NAME_SOURCES, Missing, keybase
from modules.deep_search_web import run_plan


def search(parsed, emit, stop=None):
    stop = stop or threading.Event()
    subject, mode, context = parsed["subject"], parsed["mode"], parsed["context"]
    plan = build_plan(subject, mode, context)
    result = {"status": "ok", **parsed, "activity": [], "accounts": [], "people": [], "identity": None,
              "owner_links": [], "sections": [], "source_checks": [], "plan": plan, "notes": [], "queries_run": 0}
    lock = threading.Lock()
    seen = set()

    def publish():
        if not stop.is_set():
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
                            parts = urlsplit(link["url"])
                            host = (parts.hostname or "").removeprefix("www.")
                            segments = [unquote(s).removeprefix("@") for s in parts.path.split("/") if s]
                            if segments and segments[0] in {"in", "user", "users", "profile"}:
                                segments = segments[1:]
                            alias = segments[0] if segments and host in {"github.com", "x.com", "twitter.com", "instagram.com", "linkedin.com", "reddit.com", "bsky.app", "dev.to"} else None
                            if alias and alias.casefold() == subject.casefold():
                                alias = None
                            if alias and not is_profile(link["url"], alias):
                                alias = None
                            result["owner_links"].append({**link, "alias": alias, "declared_on": data["platform"] + " · " + data["handle"]})
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
    ])
    return result
