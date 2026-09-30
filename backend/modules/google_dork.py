"""Bounded, paced Google Custom Search lookups with partial failure reporting."""
import os
import random
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import requests
from data.dorks import get_email_dorks, get_username_dorks

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


def _budget(name, default):
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def _seconds(name, default, minimum, maximum):
    try:
        return min(maximum, max(minimum, float(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


FAST_QUERY_BUDGET = _budget("DORK_FAST_BUDGET", 30)
DEEP_QUERY_BUDGET = _budget("DORK_DEEP_BUDGET", 80)
EMAIL_FAST_BUDGET = _budget("DORK_EMAIL_FAST_BUDGET", 20)
EMAIL_DEEP_BUDGET = _budget("DORK_EMAIL_DEEP_BUDGET", 60)

# Shared across all scans in one process, including requests still finishing
# after a deadline. Divide these limits by server workers for a shared key.
_CONCURRENCY = min(8, _budget("DORK_CONCURRENCY", 3))
_SLOTS = threading.BoundedSemaphore(_CONCURRENCY)
_PACE_LOCK = threading.Lock()
_NEXT_START = 0.0
_COOLDOWN_UNTIL = 0.0
_MIN_INTERVAL = _seconds("DORK_MIN_INTERVAL", 0.35, 0.1, 5)


def _failure(code, message, retryable=True):
    # Exception strings can contain provider URLs, API keys and search values.
    return {"source": "google_dork", "code": code,
            "message": message, "retryable": retryable}


class GoogleDorkEngine:
    def __init__(self, api_key="", cx_id="", delay=1.0):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self.cx_id = cx_id or os.environ.get("GOOGLE_CX_ID", "")
        self.delay = max(0, delay)
        self.results = []
        self.errors = []
        self._stop_flag = False
        self._stop = threading.Event()
        self.deadline_seconds = _seconds("DORK_DEADLINE_SECONDS", 45, 1, 120)
        self.query_timeout = _seconds("DORK_QUERY_TIMEOUT", 8, 0.1, 15)

    def stop(self):
        self._stop_flag = True
        self._stop.set()

    def _execute_query(self, query, deadline=None):
        global _NEXT_START, _COOLDOWN_UNTIL
        deadline = deadline or time.monotonic() + self.deadline_seconds
        if not self.api_key or not self.cx_id:
            return [_failure("unconfigured", "Google web search is not configured.", False)]
        for attempt in range(2):
            remaining = deadline - time.monotonic()
            if self._stop.is_set() or remaining <= 0:
                return [_failure("timeout", "Google web search reached its time limit.")]
            if not _SLOTS.acquire(timeout=remaining):
                return [_failure("busy", "Google web search is busy. Displaying other results.")]
            try:
                with _PACE_LOCK:
                    now = time.monotonic()
                    if now < _COOLDOWN_UNTIL:
                        return [_failure("rate_limited", "Google web search is cooling down. Displaying other results.")]
                    start = max(now, _NEXT_START)
                    _NEXT_START = start + max(_MIN_INTERVAL, self.delay) + random.uniform(0.05, 0.15)
                pause = max(0, start - time.monotonic())
                if self._stop.wait(min(pause, max(0, deadline - time.monotonic()))):
                    return [_failure("cancelled", "Google web search was stopped.")]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return [_failure("timeout", "Google web search reached its time limit.")]
                with _PACE_LOCK:
                    if time.monotonic() < _COOLDOWN_UNTIL:
                        return [_failure("rate_limited", "Google web search is cooling down. Displaying other results.")]
                timeout = max(0.01, min(self.query_timeout, remaining / 2))
                resp = requests.get(GOOGLE_CSE_URL, params={
                    "key": self.api_key, "cx": self.cx_id, "q": query, "num": 10,
                }, timeout=(timeout, timeout))
                if resp.status_code in (403, 429):
                    cooldown = 60 if resp.status_code == 429 else 3600
                    try:
                        cooldown = max(cooldown, int(resp.headers.get("Retry-After", 0)))
                    except (ValueError, TypeError):
                        pass
                    with _PACE_LOCK:
                        _COOLDOWN_UNTIL = max(_COOLDOWN_UNTIL, time.monotonic() + cooldown)
                    return [_failure("rate_limited" if resp.status_code == 429 else "provider_denied",
                                     "Google web search is unavailable or quota-limited. Displaying other results.",
                                     resp.status_code == 429)]
                if resp.status_code >= 500:
                    raise requests.RequestException("provider unavailable")
                if resp.status_code != 200:
                    return [_failure("provider_error", "Google web search could not complete this lookup.", False)]
                data = resp.json()
                if (not isinstance(data, dict) or "error" in data
                        or not isinstance(data.get("items", []), list)
                        or any(not isinstance(item, dict) for item in data.get("items", []))
                        or ("items" not in data and "searchInformation" not in data)):
                    return [_failure("invalid_response", "Google web search returned an unreadable response.")]
                return [{"url": item.get("link", ""), "title": item.get("title", ""),
                         "snippet": item.get("snippet", ""), "query": query,
                         "source": "google_dork"} for item in data.get("items", [])]
            except (requests.RequestException, ValueError):
                if attempt:
                    return [_failure("unavailable", "Google web search is currently unreachable. Displaying other results.")]
            except Exception:
                return [_failure("provider_error", "Google web search could not complete this lookup.")]
            finally:
                _SLOTS.release()
            if self._stop.wait(min(random.uniform(0.3, 0.7), max(0, deadline - time.monotonic()))):
                break
        return [_failure("timeout", "Google web search reached its time limit.")]

    def scan_username(self, username, callback=None, deep=False):
        return self._run_dorks(get_username_dorks(username)[:DEEP_QUERY_BUDGET if deep else FAST_QUERY_BUDGET], callback)

    def scan_email(self, email, callback=None, deep=False):
        return self._run_dorks(get_email_dorks(email)[:EMAIL_DEEP_BUDGET if deep else EMAIL_FAST_BUDGET], callback)

    def _run_dorks(self, dorks, callback=None):
        self.errors, self.results = [], []
        if self._stop_flag or not dorks:
            return []
        results = []
        deadline = time.monotonic() + self.deadline_seconds
        pool = ThreadPoolExecutor(max_workers=_CONCURRENCY)
        pending = {pool.submit(self._execute_query, dork, deadline): i for i, dork in enumerate(dorks)}
        completed = 0
        try:
            while pending and not self._stop_flag:
                ready, _ = wait(pending, timeout=max(0, deadline - time.monotonic()), return_when=FIRST_COMPLETED)
                if not ready:
                    break
                for future in ready:
                    index = pending.pop(future)
                    try:
                        hits = future.result()
                    except Exception:
                        hits = [_failure("provider_error", "A Google web search query could not complete.")]
                    successful = []
                    for hit in hits:
                        if hit.get("code"):
                            self.errors.append({**hit, "query_index": index})
                        else:
                            results.append((index, hit))
                            successful.append(hit)
                    completed += 1
                    if callback:
                        callback(module="Google Dorking", message=f"[{completed}/{len(dorks)}] Web query complete",
                                 progress=int(completed / len(dorks) * 100), results=successful)
            if pending:
                self.errors.append(_failure("cancelled" if self._stop_flag else "timeout",
                                            "Some web queries did not finish. Displaying completed results."))
        finally:
            # Avoid executor context shutdown, which waits past the scan deadline.
            if pending:
                self._stop.set()
            for future in pending:
                future.cancel()
            pool.shutdown(wait=False, cancel_futures=True)
        seen = set()
        for _, hit in sorted(results, key=lambda entry: entry[0]):
            url = hit.get("url", "")
            if url and url not in seen:
                seen.add(url)
                self.results.append(hit)
        return self.results
