"""Run real upstream tools on the fixed public controls, outside the web server.

Only normalized verdicts, timings and provenance leave this process. Native
account detection rules are unmodified. No recursive enrichment, proxies,
authentication, retries, browser impersonation or anti-block bypass is enabled.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import importlib.metadata
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

PINS = json.loads(Path(__file__).with_name("benchmark-tools.json").read_text(encoding="utf-8"))
SITE_NAMES = {"GitHub": "GitHub", "GitLab": "GitLab", "Hacker News": "HackerNews"}


def normalize_result(result):
    status = getattr(result.get("status"), "status", None)
    native = getattr(status, "name", "UNKNOWN")
    code = result.get("http_status")
    code = code if isinstance(code, int) and not isinstance(code, bool) else None
    verdict = {"CLAIMED": "found", "AVAILABLE": "not_found"}.get(native, "unknown")
    # Never credit a known upstream outage or denial as a verified absence.
    if code in (401, 403, 429) or code is not None and code >= 500:
        verdict = "unknown"
    return {"verdict": verdict, "native_status": native, "status_code": code}


def provenance(tool):
    pin = PINS[tool]
    dist = importlib.metadata.distribution(pin["package"])
    origin = json.loads(dist.read_text("direct_url.json") or "{}")
    commit = origin.get("vcs_info", {}).get("commit_id")
    if not commit and origin.get("url", "").startswith("file:"):
        # Local validation installs an exact checked-out upstream commit.
        path = unquote(urlparse(origin["url"]).path)
        if os.name == "nt":
            path = path.lstrip("/")
        commit = subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"], text=True).strip()
        if subprocess.check_output(["git", "-C", path, "status", "--porcelain"], text=True).strip():
            raise ValueError("Upstream source has local changes")
    if dist.version != pin["version"] or commit != pin["commit"]:
        raise ValueError("Installed tool does not match the published pin")
    return {**pin, "status": "measured", "timeout_seconds": 8, "max_connections": 3,
            "parsing": False, "enrichment": False, "retries": 0,
            "python_version": sys.version.split()[0],
            "requests_version": importlib.metadata.version("requests")}


def execute(tool, dataset):
    metadata = provenance(tool)
    if tool == "sherlock":
        import sherlock_project
        from sherlock_project.sherlock import sherlock
        from sherlock_project.notify import QueryNotify
        catalogue = json.loads((Path(sherlock_project.__file__).parent / "resources/data.json").read_text(encoding="utf-8"))
        selected = {SITE_NAMES[name]: catalogue[SITE_NAMES[name]] for name in dataset["platforms"] if SITE_NAMES.get(name) in catalogue}
        def search(handle):
            # Sherlock uses one worker per selected site for this small scope.
            return sherlock(handle, json.loads(json.dumps(selected)), QueryNotify(), timeout=8)
        fingerprint = selected
    else:
        import maigret
        from maigret.sites import MaigretDatabase
        catalogue = json.loads((Path(maigret.__file__).parent / "resources/data.json").read_text(encoding="utf-8"))
        selected = {SITE_NAMES[name]: catalogue["sites"][SITE_NAMES[name]] for name in dataset["platforms"] if SITE_NAMES.get(name) in catalogue["sites"]}
        fingerprint = {"sites": selected, "engines": catalogue.get("engines", {})}
        def search(handle):
            db = MaigretDatabase().load_from_json(json.loads(json.dumps(fingerprint)))
            sites = {name: site for name, site in db.sites_dict.items() if not site.disabled and not site.protection}
            logger = logging.getLogger("benchmark-maigret")
            logger.setLevel(logging.CRITICAL)
            return asyncio.run(maigret.search(handle, sites, logger, timeout=8, max_connections=3,
                is_parsing_enabled=False, is_enrich_enabled=False, retries=0, no_progressbar=True,
                check_domains=False, cloudflare_bypass=None, dns_resolver="threaded"))
    metadata["site_database_sha256"] = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    controls = []
    for handle in dataset["usernames"]:
        # Discard tool logs and profile bodies; publish only this allowlist.
        start = time.monotonic()
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                results = search(handle)
            duration = round(time.monotonic() - start, 3)
            checks = {name: normalize_result(results[SITE_NAMES[name]]) if SITE_NAMES.get(name) in results
                      else {"verdict": "unknown", "reason_code": "unsupported_or_disabled"}
                      for name in dataset["platforms"]}
        except Exception:
            duration = None
            checks = {name: {"verdict": "unknown", "reason_code": "tool_failed"} for name in dataset["platforms"]}
        controls.append({"username": handle, "duration_seconds": duration, "checks": checks})
        time.sleep(.3)
    return {"metadata": metadata, "controls": controls}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", choices=list(PINS), required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = execute(args.tool, json.loads(args.dataset.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(data), encoding="utf-8")
