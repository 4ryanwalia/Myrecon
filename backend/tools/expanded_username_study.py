"""Bounded, opt-in study of published upstream test fixtures and negative controls.

Python 3.12; install requirements-benchmark.txt. Prepare once, review the
platform-scoped manifest, then run. Never expands a handle to other platforms.
Reference evidence is collected before predictions; fixture expectations never
become reference truth. No personal handles, credentials or profile bodies.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
from datetime import datetime, timezone
import hashlib
import html
import importlib.metadata
import io
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
import time

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from modules.sweep import CATALOGUE, Sweep
from benchmark_worker import PINS, normalize_result, provenance
from daily_benchmark import reference_label, summarize, utc_now

TOOLS = ("myrecon", "sherlock", "maigret")
ID = "username-controls-2026-11-01"
MANIFEST = ROOT / "backend/data/username-study-controls.json"
MAPPINGS = {
    "GitHub": ("GitHub", "GitHub"),
    "GitLab": ("GitLab", "GitLab"),
    "Hacker News": ("HackerNews", "HackerNews"),
    "Docker Hub": ("Docker Hub", "Docker Hub"),
    "Dev.to": ("DEV Community", "DEV Community"),
    "npm": ("npm", "NPM"),
    "Keybase": ("Keybase", "Keybase"),
    "PyPI": ("PyPi", "PyPi"),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def catalogues():
    import sherlock_project
    import maigret
    paths = {"sherlock": Path(sherlock_project.__file__).parent / "resources/data.json",
             "maigret": Path(maigret.__file__).parent / "resources/data.json"}
    return {t: json.loads(p.read_text(encoding="utf-8")) for t, p in paths.items()}


def prepare(output=MANIFEST):
    raw = catalogues()
    for tool in PINS:
        provenance(tool)  # Reject drift before copying fixtures.
    sites = {"sherlock": raw["sherlock"], "maigret": raw["maigret"]["sites"]}
    cases, rules = [], {}
    for platform, names in MAPPINGS.items():
        grouped = {}
        rules[platform] = {}
        for tool, name in zip(("sherlock", "maigret"), names):
            rule = sites[tool][name]
            rules[platform][tool] = {"site_name": name, "rule": rule,
                "sha256": digest(json.dumps(rule, sort_keys=True).encode()),
                "source_url": f"{PINS[tool]['repository']}/blob/{PINS[tool]['commit']}/"
                    + ("sherlock_project" if tool == "sherlock" else "maigret") + "/resources/data.json"}
            fields = (("username_claimed", "upstream_claimed_fixture"),) if tool == "sherlock" else (
                ("usernameClaimed", "upstream_claimed_fixture"), ("usernameUnclaimed", "upstream_unclaimed_fixture"))
            for field, kind in fields:
                handle = rule.get(field)
                if not handle:
                    continue
                # GitHub/GitLab/PyPI aliases differing only by case are one
                # namespace; Hacker News IDs remain case-sensitive.
                key = handle if platform == "Hacker News" else handle.casefold()
                entry = grouped.setdefault(key, {"platform": platform, "handle": handle,
                    "cohort": kind, "fixture_sources": []})
                if entry["cohort"] != kind:
                    raise ValueError("Conflicting fixture expectations")
                entry["fixture_sources"].append({"tool": tool, "field": field,
                    "site_name": name, "source_url": rules[platform][tool]["source_url"]})
        cases.extend(grouped.values())
        for index in range(2):
            # Short alphanumeric values avoid common username grammar errors.
            handle = "mr26" + digest(f"{ID}/{platform}/{index}".encode())[:10]
            cases.append({"platform": platform, "handle": handle,
                "cohort": "synthetic_negative_candidate", "fixture_sources": [],
                "generation": f"mr26 + first 10 hex SHA256({ID}/{platform}/{index})"})
    for i, case in enumerate(cases, 1):
        case["id"] = f"C{i:02d}"
    data = {"schema_version": 1, "id": ID, "created_at_utc": utc_now(),
        "selection": "Eight developer/community platforms with explicit upstream fixtures and reviewable public references. Every fixture stays on its source platform. Two deterministic synthetic candidates per platform. Sample fixed before predictions.",
        "ownership": "Published upstream testing fixtures, not accounts owned by MyRecon or the user. Account existence does not establish identity. No personal social-media handles or customer history are included.",
        "reference_policy": "Fixture labels and generated randomness are expectations only. Current exact account evidence or explicit absence supplies the reference; failures stay unknown.",
        "platforms": list(MAPPINGS), "cases": cases, "rules": rules, "tool_pins": PINS}
    write(output, data)
    return data


def reference_evidence(platform, handle, code, data, title=""):
    """Allowlisted source facts, never a whole profile or tool consensus."""
    if platform in ("GitHub", "GitLab", "Hacker News"):
        verdict = reference_label(platform, handle, code, data)
        if platform == "GitHub":
            facts = {k: data[k] for k in ("login", "id", "type") if isinstance(data, dict) and k in data}
        elif platform == "GitLab":
            facts = {"users": [{k: u[k] for k in ("id", "username") if k in u}
                for u in data if isinstance(u, dict)]} if isinstance(data, list) else {}
        else:
            facts = {k: data[k] for k in ("id", "created") if isinstance(data, dict) and k in data}
            if code == 200 and data is None:
                facts = {"response": None}
        return verdict, "typed_official_api" if verdict != "unknown" else "reference_unresolved", facts
    if platform in ("Docker Hub", "Dev.to"):
        if code == 404:
            return "not_found", "explicit_api_absence", {"status": 404}
        if code == 200 and isinstance(data, dict) and data.get("username", "").casefold() == handle.casefold() and data.get("id"):
            if platform == "Docker Hub" or data.get("type_of") == "user":
                return "found", "typed_official_api", {k: data[k] for k in ("id", "username", "type_of") if k in data}
    if platform == "npm" and code == 200 and isinstance(data, dict):
        if data.get("name", "").casefold() == handle.casefold() and data.get("_id") == f"org.couchdb.user:{handle}":
            return "found", "typed_official_api", {"name": data["name"], "_id": data["_id"]}
        # The registry may disable this endpoint; a generic 404 is not a
        # verified negative without a documented account-specific response.
    if platform == "Keybase" and code == 200 and isinstance(data, dict):
        status = data.get("status", {})
        person = data.get("them")
        if status.get("code") == 205 and person is None:
            return "not_found", "typed_api_absence", {"status_code": 205, "them": None}
        if status.get("code") == 0 and isinstance(person, dict) and person.get("id") and person.get("basics", {}).get("username", "").casefold() == handle.casefold():
            return "found", "typed_official_api", {"id": person["id"], "username": person["basics"]["username"]}
    if platform == "PyPI":
        if code == 404 and re.search(r"(?:not found|404)", title, re.I):
            return "not_found", "explicit_missing_profile", {"title": title}
        match = re.fullmatch(r"Profile of (.+?)\s*[·|]\s*PyPI", title)
        if code == 200 and match and match[1].casefold() == handle.casefold():
            return "found", "exact_profile_title", {"title": title}
    return "unknown", "reference_unresolved", {"title": title} if title else {}


def observe(case):
    platform = next(p for p in CATALOGUE if p["name"] == case["platform"])
    url = (platform.get("api") or platform["url"]).replace("{username}", case["handle"])
    result = {"url": url, "started_at_utc": utc_now(), "verdict": "unknown",
              "evidence": "request_failed", "status_code": None, "facts": {}}
    try:
        with requests.Session() as session:
            with session.get(url, headers={"User-Agent": "MyRecon-public-control-study/1.0"}, timeout=(6, 8), stream=True) as response:
                body = bytearray()
                for chunk in response.iter_content(16384):
                    body.extend(chunk)
                    if len(body) > 524288:
                        result.update(evidence="response_too_large", status_code=response.status_code)
                        break
                else:
                    raw = body.decode(response.encoding or "utf-8", errors="replace")
                    try:
                        data = json.loads(raw)
                    except ValueError:
                        data = None
                    # A malformed HN JSON response must not become JSON null.
                    json_valid = True
                    try:
                        json.loads(raw)
                    except ValueError:
                        json_valid = False
                    title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
                    title = html.unescape(re.sub(r"\s+", " ", title[1])).strip()[:240] if title else ""
                    verdict, evidence, facts = reference_evidence(case["platform"], case["handle"], response.status_code, data, title)
                    if case["platform"] != "PyPI" and response.status_code == 200 and not json_valid:
                        verdict, evidence, facts = "unknown", "invalid_json", {}
                    result.update(verdict=verdict, evidence=evidence, facts=facts,
                        status_code=response.status_code, final_url=response.url,
                        body_sha256=digest(body), body_bytes=len(body),
                        content_type=response.headers.get("Content-Type", ""))
    except requests.RequestException as exc:
        result["error_type"] = type(exc).__name__
    result["finished_at_utc"] = utc_now()
    return result


def normalize(check):
    result = normalize_result(check)
    code = result["status_code"]
    if code is not None and (code < 200 or 300 <= code < 400 or code >= 400 and code not in (404, 410)):
        result["verdict"] = "unknown"
        result["reason_code"] = "http_denial_or_error"
    return result


def predict(tool, case, manifest):
    start = time.monotonic()
    result = {"verdict": "unknown", "reason_code": "tool_failed"}
    if tool == "myrecon":
        platform = next(p for p in CATALOGUE if p["name"] == case["platform"])
        hits, _ = Sweep(case["handle"], deadline_seconds=45, concurrency=1).run(platforms=[platform])
        if len(hits) == 1:
            result = {k: hits[0].get(k) for k in ("verdict", "url", "status_code", "confidence", "reason_code")}
    else:
        selected = manifest["rules"][case["platform"]][tool]
        name, rule = selected["site_name"], selected["rule"]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if tool == "sherlock":
                from sherlock_project.sherlock import sherlock
                from sherlock_project.notify import QueryNotify
                # Respect the pinned, captured upstream exclusion list.
                if name in manifest["sherlock_exclusions"]["sites"]:
                    result = {"verdict": "unknown", "reason_code": "upstream_excluded"}
                    results = {}
                else:
                    results = sherlock(case["handle"], {name: json.loads(json.dumps(rule))}, QueryNotify(), timeout=8)
            else:
                import maigret
                from maigret.sites import MaigretDatabase
                db = MaigretDatabase().load_from_json({"sites": {name: rule}, "engines": manifest["maigret_engines"]})
                sites = {n: s for n, s in db.sites_dict.items() if not s.disabled and not s.protection and s.type == "username"}
                if not sites:
                    result = {"verdict": "unknown", "reason_code": "unsupported_disabled_or_protected"}
                    results = {}
                else:
                    logger = logging.getLogger("expanded-study")
                    logger.setLevel(logging.CRITICAL)
                    results = asyncio.run(maigret.search(case["handle"], sites, logger, timeout=8,
                        max_connections=1, is_parsing_enabled=False, is_enrich_enabled=False,
                        retries=0, no_progressbar=True, check_domains=False, cloudflare_bypass=None, dns_resolver="threaded"))
            if name in results:
                native = results[name]
                result = {**normalize(native), "url": native.get("url_user", ""),
                    "similar_search": bool(native.get("is_similar", False))}
    code = result.get("status_code")
    if code is not None and (code < 200 or 300 <= code < 400 or code >= 400 and code not in (404, 410)):
        result.update(verdict="unknown", reason_code="http_denial_or_error")
    result["duration_seconds"] = round(time.monotonic() - start, 3)
    return result


def outcome(reference, prediction):
    actual, truth = prediction["verdict"], reference["verdict"]
    if truth == "unknown":
        return "unscored_reference"
    if actual == "unknown":
        return "unresolved_prediction"
    return {("found", "found"): "supported_match", ("not_found", "found"): "false_positive",
            ("found", "not_found"): "false_negative", ("not_found", "not_found"): "supported_absence"}[truth, actual]


def tool_summary(rows, tool):
    counts = summarize(rows, tool)
    claims = [r for r in rows if r[tool].get("native_status") == "CLAIMED" or tool == "myrecon" and r[tool]["verdict"] == "found"]
    return {**counts, "reported_claims": len(claims),
        "source_supported_claims": sum(r["reference"]["verdict"] == "found" for r in claims),
        "source_contradicted_claims": sum(r["reference"]["verdict"] == "not_found" for r in claims),
        "unresolved_claims": sum(r["reference"]["verdict"] == "unknown" for r in claims),
        "unknown_predictions": sum(r[tool]["verdict"] == "unknown" for r in rows),
        "unresolved_checks": sum(r[tool]["verdict"] == "unknown" or r["reference"]["verdict"] == "unknown" for r in rows)}


def execute(manifest_path, output):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["tool_pins"] != PINS or set(manifest["platforms"]) != set(MAPPINGS):
        raise ValueError("Unexpected study manifest")
    # Validate every snapshot against installed immutable upstream rules.
    raw = catalogues()
    for platform in manifest["platforms"]:
        for tool in ("sherlock", "maigret"):
            entry = manifest["rules"][platform][tool]
            installed = (raw[tool] if tool == "sherlock" else raw[tool]["sites"])[entry["site_name"]]
            if entry["rule"] != installed or digest(json.dumps(installed, sort_keys=True).encode()) != entry["sha256"]:
                raise ValueError("Site rule drift")
    from sherlock_project.sites import EXCLUSIONS_URL
    exclusions = requests.get(EXCLUSIONS_URL, timeout=(6, 10))
    exclusions.raise_for_status()
    manifest["sherlock_exclusions"] = {"url": EXCLUSIONS_URL, "checked_at_utc": utc_now(),
        "sha256": digest(exclusions.content), "sites": exclusions.text.splitlines()}
    manifest["maigret_engines"] = raw["maigret"].get("engines", {})
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    hashes = {rel: digest((ROOT / rel).read_bytes()) for rel in (
        "backend/modules/sweep.py", "backend/modules/profile_identity.py", "backend/modules/username_integrations.py",
        "backend/data/platforms_full.json", "backend/data/platforms_extra.json",
        "backend/tools/expanded_username_study.py", "backend/tools/benchmark_worker.py", "backend/tools/daily_benchmark.py")}
    metadata = {"myrecon": {"label": "MyRecon", "version": commit[:8], "commit": commit,
        "scope": "Web engine; eight selected platforms; Android and hosted UI not measured",
        "status": "measured", "max_connections": 1, "deadline_seconds": 45,
        "connect_timeout_seconds": 6, "read_timeout_seconds": 8,
        "python_version": sys.version.split()[0], "requests_version": requests.__version__,
        "selected_catalogue_sha256": digest(json.dumps([p for p in CATALOGUE if p["name"] in MAPPINGS], sort_keys=True).encode())}}
    for tool in ("sherlock", "maigret"):
        metadata[tool] = {**provenance(tool), "max_connections": 1,
            "selected_rules_sha256": digest(json.dumps({p: manifest["rules"][p][tool] for p in manifest["platforms"]}, sort_keys=True).encode())}
    document = {"schema_version": 1, "id": manifest["id"], "started_at_utc": utc_now(),
        "status": "collecting_references", "manifest_sha256": digest(manifest_path.read_bytes()),
        "manifest": manifest, "source_hashes": hashes, "tool_metadata": metadata,
        "environment": {"network": "local Windows workstation", "platform_concurrency": 1,
            "order": "All reference observations first, then MyRecon, Sherlock, Maigret in sequence",
            "cache": "Application cache bypassed; upstream/provider caches not controlled",
            "authentication": "No supplied credentials, cookies, proxies or block bypass. Native response cookies may be handled by upstream libraries.",
            "retries": 0, "parsing": False, "enrichment": False}, "checks": []}
    for case in manifest["cases"]:
        document["checks"].append({**case, "reference": observe(case)})
        write(output, document)
        print(f"Reference {case['id']} {case['platform']}: {document['checks'][-1]['reference']['verdict']}", flush=True)
        time.sleep(.3)
    for tool in TOOLS:
        document["status"] = f"measuring_{tool}"
        document["tool_metadata"][tool]["started_at_utc"] = utc_now()
        for row in document["checks"]:
            started = utc_now()
            try:
                row[tool] = predict(tool, row, manifest)
            except Exception as exc:
                row[tool] = {"verdict": "unknown", "reason_code": "tool_failed",
                    "error_type": type(exc).__name__, "duration_seconds": None}
            row[tool].update(started_at_utc=started, finished_at_utc=utc_now())
            row[tool]["outcome"] = outcome(row["reference"], row[tool])
            write(output, document)
            print(f"{tool} {row['id']}: {row[tool]['outcome']}", flush=True)
            time.sleep(.3)
        document["tool_metadata"][tool]["finished_at_utc"] = utc_now()
    document.update(status="measured", finished_at_utc=utc_now(),
        summaries={t: tool_summary(document["checks"], t) for t in TOOLS})
    write(output, document)
    print(json.dumps(document["summaries"], indent=2), flush=True)
    return document


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        data = prepare(args.manifest)
        print(f"Prepared {len(data['cases'])} platform-scoped controls")
    else:
        if not args.output:
            parser.error("--output is required for a measured run")
        execute(args.manifest, args.output)
