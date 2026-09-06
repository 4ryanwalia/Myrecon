"""
╔══════════════════════════════════════════════════════════════╗
║  Google Dorking Module — Google Custom Search API            ║
║  Free: 100 queries/day — No paid key required               ║
╚══════════════════════════════════════════════════════════════╝

HOW TO GET YOUR FREE API KEY:
  1. Go to https://console.cloud.google.com/
  2. Create a project → Enable "Custom Search API"
  3. Go to Credentials → Create API Key
  4. Go to https://programmablesearchengine.google.com/
  5. Create a search engine → Toggle "Search the entire web"
  6. Copy the Search Engine ID (CX)
"""

import time
import os
import requests

from data.dorks import get_username_dorks, get_email_dorks

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


def _budget(env_name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(env_name, default)))
    except (TypeError, ValueError):
        return default


# The free Custom Search tier allows 100 queries per day across every scan the
# server runs. The username corpus is ~770 queries long, so running it end to
# end would spend the whole day's allowance on one search and return quota
# errors for everything after it. These budgets keep a single scan affordable;
# get_username_dorks() orders its output highest-precision first so the budget
# is spent on queries whose hits are profile URLs rather than incidental page
# mentions. Raise them on a paid key.
FAST_QUERY_BUDGET = _budget("DORK_FAST_BUDGET", 30)
DEEP_QUERY_BUDGET = _budget("DORK_DEEP_BUDGET", 80)
EMAIL_FAST_BUDGET = _budget("DORK_EMAIL_FAST_BUDGET", 20)
EMAIL_DEEP_BUDGET = _budget("DORK_EMAIL_DEEP_BUDGET", 60)


class GoogleDorkEngine:
    """Executes Google dork queries through Google Custom Search API."""

    def __init__(self, api_key: str = "", cx_id: str = "", delay: float = 1.0):
        # Keys come only from the caller or the environment — never hardcoded.
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.cx_id = cx_id or os.environ.get("GOOGLE_CX_ID", "")
        self.delay = delay
        self.results: list[dict] = []
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def _execute_query(self, query: str) -> list[dict]:
        hits = []
        if self.api_key and self.cx_id:
            try:
                resp = requests.get(GOOGLE_CSE_URL, params={
                    "key": self.api_key, "cx": self.cx_id,
                    "q": query, "num": 10,
                }, timeout=15)
                data = resp.json()
                if "items" in data:
                    for item in data["items"]:
                        hits.append({
                            "url": item.get("link", ""),
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "query": query,
                            "source": "google_dork",
                        })
                elif "error" in data:
                    hits.append({
                        "url": "", "title": f"API Error: {data['error'].get('message','')}",
                        "snippet": "", "query": query, "source": "google_dork", "error": True,
                    })
            except Exception as e:
                hits.append({
                    "url": "", "title": f"Error: {e}", "snippet": "",
                    "query": query, "source": "google_dork", "error": True,
                })
        else:
            # Simulation mode
            hits.append({
                "url": self._simulate_url(query),
                "title": f"[Simulated] {query}",
                "snippet": "API key not set — showing expected target URL.",
                "query": query, "source": "google_dork", "simulated": True,
            })
        return hits

    @staticmethod
    def _simulate_url(query: str) -> str:
        if "site:" in query:
            domain = query.split("site:", 1)[1].split('"')[0].strip().split()[0]
            return f"https://{domain}"
        return f"https://www.google.com/search?q={query}"

    def scan_username(self, username: str, callback=None, deep: bool = False) -> list[dict]:
        dorks = get_username_dorks(username)
        return self._run_dorks(
            dorks[:DEEP_QUERY_BUDGET if deep else FAST_QUERY_BUDGET], callback
        )

    def scan_email(self, email: str, callback=None, deep: bool = False) -> list[dict]:
        dorks = get_email_dorks(email)
        return self._run_dorks(
            dorks[:EMAIL_DEEP_BUDGET if deep else EMAIL_FAST_BUDGET], callback
        )

    def _run_dorks(self, dorks: list[str], callback=None) -> list[dict]:
        results = []
        total = len(dorks)
        for i, dork in enumerate(dorks):
            if self._stop_flag:
                break
            hits = self._execute_query(dork)
            results.extend(hits)
            if callback:
                callback(module="Google Dorking", message=f"[{i+1}/{total}] {dork[:80]}",
                         progress=int(((i+1)/total)*100), results=hits)
            time.sleep(self.delay)

        seen = set()
        unique = []
        for r in results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(r)
        self.results = unique
        return unique
