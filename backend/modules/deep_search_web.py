"""Execute the app's query plan with bounded search and verified constraints."""
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from modules.deep_search_plan import accepts
from modules.deep_search_sources import PublicClient, plain
from modules.google_dork import GoogleDorkEngine

_PACE = threading.Lock()
_NEXT = 0.0


def run_plan(plan, on_hits, stop):
    selected = [q for q in plan if q.get("scheduled")]
    engine = GoogleDorkEngine(delay=0.35)
    if engine.api_key and engine.cx_id:
        def relay(**ev):
            for hit in ev.get("results", []):
                query = next((q for q in selected if q["text"] == hit.get("query")), None)
                if query and accepts(query["text"], hit):
                    on_hits(query, [{**hit, "engine": "Google Custom Search"}])
        engine._run_dorks([q["text"] for q in selected], relay)
        failed = {e.get("query_index") for e in engine.errors}
        incomplete = any(e.get("query_index") is None for e in engine.errors)
        for index, q in enumerate(selected):
            q["executed"] = index not in failed and not incomplete
        return ["Some indexed-web queries were unavailable. Browser query links remain available."] if engine.errors else []

    # Keyless sources can refuse datacentre addresses. Stop at a challenge;
    # never solve, circumvent or treat it as an empty result.
    blocked, errors = set(), []
    deadline = time.monotonic() + 40
    for q in selected:
        if stop.is_set() or time.monotonic() >= deadline or len(blocked) == 2:
            break
        for provider in ("DuckDuckGo", "Bing"):
            if provider in blocked:
                continue
            try:
                global _NEXT
                with _PACE:
                    start = max(time.monotonic(), _NEXT)
                    _NEXT = start + 1.2
                if stop.wait(max(0, min(start - time.monotonic(), deadline - time.monotonic()))):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                c = PublicClient(min(8, remaining))
                if provider == "DuckDuckGo":
                    body = c.get("https://lite.duckduckgo.com/lite/", {"q": q["text"]}, accept="text/html", text=True)
                    if "anomaly.js" in body or "challenge-form" in body:
                        raise ValueError("challenge")
                    soup = BeautifulSoup(body, "html.parser")
                    links, snippets = soup.select("a.result-link"), soup.select(".result-snippet")
                    if not links and "No results" not in body and "no-results" not in body:
                        raise ValueError("unrecognised response")
                    hits = []
                    for i, anchor in enumerate(links):
                        href = anchor.get("href", "")
                        href = parse_qs(urlsplit(href).query).get("uddg", [href])[0]
                        hits.append({"url": href, "title": plain(anchor.get_text()), "snippet": plain(snippets[i].get_text()) if i < len(snippets) else ""})
                else:
                    body = c.get("https://www.bing.com/search", {"q": q["text"], "format": "rss", "count": 20}, accept="application/rss+xml", text=True)
                    root = ET.fromstring(body)
                    if root.tag != "rss" or root.find("channel") is None:
                        raise ValueError("unrecognised response")
                    hits = [{"url": x.findtext("link", ""), "title": plain(x.findtext("title")), "snippet": plain(x.findtext("description"))} for x in root.findall("./channel/item")]
                q["executed"] = True
                hits = [{**h, "engine": provider, "query": q["text"]} for h in hits if accepts(q["text"], h)][:8]
                on_hits(q, hits)
                if hits:
                    break
            except Exception:
                blocked.add(provider)
    if blocked or any(not q["executed"] for q in selected):
        errors.append("Some indexed-web queries could not run from this server. Open the query links in your browser to continue. An empty section does not prove absence.")
    return errors
