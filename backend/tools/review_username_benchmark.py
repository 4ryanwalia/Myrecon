"""Collect independent source observations for every reported profile address.

HTTP 200 and a tool's own verdict are never reference truth. Typed APIs,
explicit missing pages, and human-reviewed source evidence supply labels.
Unresolved pages stay unverified. No cookies, authentication or retries.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

import requests

from daily_benchmark import reference_label, utc_now
from username_benchmark import write


def address(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    host = {"buymeacoff.ee": "buymeacoffee.com"}.get(host, host)
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), parts.query, ""))


def observe(url, handle):
    result = {"url": url, "checked_at_utc": utc_now(), "verdict": "unknown", "evidence": "unverified"}
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "MyRecon-public-benchmark-review/1.0", "Accept": "text/html,application/json"})
            with session.get(url, timeout=(6, 8), stream=True) as response:
                result.update(status_code=response.status_code, final_url=response.url)
                body = b""
                for chunk in response.iter_content(16384):
                    body += chunk
                    if len(body) >= 512000:
                        break
                raw = body.decode(response.encoding or "utf-8", errors="replace")
                title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
                title = html.unescape(re.sub(r"\s+", " ", title.group(1))).strip()[:240] if title else ""
                result.update(title=title, body_sha256=hashlib.sha256(body).hexdigest())
                if response.status_code in (404, 410):
                    result.update(verdict="not_found", evidence="explicit_http_absence")
                elif response.status_code != 200:
                    result["evidence"] = "blocked_or_unavailable"
                elif re.match(r"^(?:404(?:\b|\s)|page not found\b|not found$|user not found\b|profile not found\b)", title, re.I):
                    result.update(verdict="not_found", evidence="explicit_missing_title")
                if urlsplit(url).hostname == "rubygems.org" and title.startswith("Profile of "):
                    named_handle = title.removeprefix("Profile of ").split(" | ")[0]
                    if named_handle.casefold() != handle.casefold():
                        result.update(verdict="not_found", evidence="different_profile_handle",
                                      observed_handle=named_handle)
                host = (urlsplit(url).hostname or "").removeprefix("www.")
                if host in ("bangumi.tv", "bgm.tv"):
                    final_path = urlsplit(response.url).path.rstrip("/")
                    if final_path.startswith("/user/") and final_path != f"/user/{handle}":
                        result.update(verdict="not_found", evidence="different_profile_handle",
                                      observed_handle=final_path.removeprefix("/user/"))
                apis = {"github.com": ("GitHub", f"https://api.github.com/users/{handle}"),
                        "news.ycombinator.com": ("Hacker News", f"https://hacker-news.firebaseio.com/v0/user/{handle}.json"),
                        "hub.docker.com": ("Docker Hub", f"https://hub.docker.com/v2/users/{handle}/")}
                if host in apis:
                    platform, api = apis[host]
                    reference = session.get(api, timeout=(6, 8))
                    data = reference.json() if reference.status_code == 200 else None
                    verdict = reference_label(platform, handle, reference.status_code, data)
                    if platform == "Docker Hub":
                        verdict = "found" if (reference.status_code == 200 and isinstance(data, dict)
                            and data.get("username", "").casefold() == handle.casefold()
                            and isinstance(data.get("id"), (int, str)) and bool(data.get("id"))) else "not_found" if reference.status_code == 404 else "unknown"
                    result.update(verdict=verdict, evidence="typed_official_api" if verdict != "unknown" else "api_unavailable",
                                  reference_url=api, reference_status_code=reference.status_code)
    except (requests.RequestException, ValueError):
        result["evidence"] = "request_failed"
    return result


def collect(folder, handle):
    urls = {}
    for tool in ("myrecon", "sherlock", "maigret", "sherlock-bundled-diagnostic"):
        path = folder / f"{tool}.json"
        if not path.exists():
            continue
        for name, check in json.loads(path.read_text())["controls"][0]["checks"].items():
            if (check["verdict"] == "found" or check.get("native_status") == "CLAIMED") and check.get("url"):
                urls.setdefault(address(check["url"]), check["url"])
    previous_path = folder / "source-reviews.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    pending = {key: url for key, url in urls.items() if key not in previous}
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(observe, url, handle): key for key, url in pending.items()}
        for job in as_completed(jobs):
            key = jobs[job]
            previous[key] = job.result()
            write(previous_path, previous)
            print(f"Source review {len(previous)}/{len(urls)}: {key} {previous[key]['evidence']}", flush=True)
    return previous


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output_dir, args.username)
