"""Public, fixed-sample regression benchmark. Never consumes user searches.

Run from the repo root: python backend/tools/daily_benchmark.py
Reference labels come from typed official API responses. They can be unknown.
The sample shares some API evidence with Sweep; it is not an independent audit
or a whole-catalogue accuracy estimate. Only aggregate counts and public controls
are retained, never profile contents, avatars, tokens or private identifiers.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from modules.sweep import CATALOGUE, Sweep, UA  # noqa: E402

DATASET = ROOT / "backend/data/benchmark-usernames.json"
OUTPUT = ROOT / "frontend/data/benchmarks.json"
NAMED_TOOLS = json.loads(Path(__file__).with_name("benchmark-tools.json").read_text(encoding="utf-8"))


def named_tool(tool, dataset, python=sys.executable):
    """Isolate third-party dependencies and bound the entire batch runtime."""
    with tempfile.TemporaryDirectory(prefix="myrecon-benchmark-") as scratch:
        data_path, result_path = Path(scratch) / "dataset.json", Path(scratch) / "result.json"
        data_path.write_text(json.dumps(dataset), encoding="utf-8")
        try:
            subprocess.run([str(python), str(Path(__file__).with_name("benchmark_worker.py")),
                            "--tool", tool, "--dataset", str(data_path), "--output", str(result_path)],
                           timeout=420, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result["metadata"]["commit"] != NAMED_TOOLS[tool]["commit"]:
                raise ValueError("Unexpected tool revision")
            controls = result["controls"]
            if [c["username"] for c in controls] != dataset["usernames"]:
                raise ValueError("Unexpected control list")
            for control in controls:
                if set(control["checks"]) != set(dataset["platforms"]):
                    raise ValueError("Unexpected platform list")
                if any(check.get("verdict") not in ("found", "not_found", "unknown") for check in control["checks"].values()):
                    raise ValueError("Unexpected verdict")
                duration = control["duration_seconds"]
                if duration is not None and (not isinstance(duration, (int, float)) or duration < 0):
                    raise ValueError("Invalid timing")
            return result
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
            return {"metadata": {**NAMED_TOOLS[tool], "status": "unavailable"},
                    "controls": [{"username": handle, "duration_seconds": None,
                                  "checks": {name: {"verdict": "unknown", "reason_code": "tool_unavailable"}
                                             for name in dataset["platforms"]}} for handle in dataset["usernames"]]}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def reference_label(platform, handle, code, data):
    """HTTP success alone is never a reference label."""
    if platform == "GitHub" and code == 404:
        return "not_found"
    if code != 200:
        return "unknown"
    if platform == "GitHub":
        if isinstance(data, dict) and isinstance(data.get("id"), int) and str(data.get("login", "")).lower() == handle.lower():
            return "found"
    elif platform == "GitLab" and isinstance(data, list):
        if not data:
            return "not_found"
        if any(isinstance(item, dict) and isinstance(item.get("id"), int) and str(item.get("username", "")).lower() == handle.lower() for item in data):
            return "found"
    elif platform == "Hacker News":
        if data is None:
            return "not_found"
        if isinstance(data, dict) and data.get("id") == handle and isinstance(data.get("created"), int):
            return "found"
    return "unknown"


def reference(session, platform, handle):
    url = platform["api"].replace("{username}", handle)
    headers = {"User-Agent": "MyRecon-public-benchmark/1.0", "Accept": "application/json"}
    # Used only on api.github.com. Never published in raw evidence.
    if platform["name"] == "GitHub" and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    label, code = "unknown", None
    try:
        with session.get(url, headers=headers, timeout=(6, 8)) as response:
            code = response.status_code
            data = response.json() if code == 200 else None
            label = reference_label(platform["name"], handle, code, data)
    except (requests.RequestException, ValueError):
        pass
    return {"verdict": label, "status_code": code, "source_url": url, "checked_at_utc": utc_now()}


def status_baseline(session, platform, handle):
    """Explicit HTTP-200 heuristic, not a named conventional tool."""
    code, verdict = None, "unknown"
    try:
        with session.get(platform["url"].replace("{username}", handle),
                         headers={"User-Agent": UA}, timeout=(6, 8), stream=True) as response:
            code = response.status_code
            if code == 200:
                verdict = "found"
            elif code in (404, 410):
                verdict = "not_found"
    except requests.RequestException:
        pass
    return {"verdict": verdict, "status_code": code}


def summarize(rows, tool):
    counts = dict.fromkeys(("TP", "TN", "FP", "FN", "unknown", "unscored", "unknown_negative"), 0)
    for row in rows:
        expected, actual = row["reference"]["verdict"], row[tool]["verdict"]
        if expected == "unknown":
            counts["unscored"] += 1
        elif actual == "unknown":
            counts["unknown"] += 1
            counts["unknown_negative"] += int(expected == "not_found")
        else:
            bucket = {("found", "found"): "TP", ("found", "not_found"): "FN",
                      ("not_found", "found"): "FP", ("not_found", "not_found"): "TN"}[(expected, actual)]
            counts[bucket] += 1
    negatives = counts["TN"] + counts["FP"]
    scored = sum(counts[key] for key in ("TP", "TN", "FP", "FN"))
    return {**counts, "total": len(rows), "scored": scored,
            "negative_denominator": negatives,
            "false_positive_rate_percent": round(100 * counts["FP"] / negatives, 2) if negatives else None,
            "accuracy_percent": round(100 * (counts["TP"] + counts["TN"]) / scored, 2) if scored else None,
            "coverage_percent": round(100 * scored / len(rows), 2) if rows else 0}


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 3)


def execute(dataset, tool_python=sys.executable, require_named=False):
    handles = dataset["usernames"]
    if len(handles) != 10 or len(set(handles)) != 10:
        raise ValueError("The public benchmark requires exactly ten unique usernames")
    platforms = [next(p for p in CATALOGUE if p["name"] == name) for name in dataset["platforms"]]
    started, rows, timings, baseline_timings = utc_now(), [], [], []
    with requests.Session() as session:
        for handle in handles:
            truth = {}
            for platform in platforms:
                truth[platform["name"]] = reference(session, platform, handle)
                time.sleep(.3)  # Small fixed workload, paced without retries or block evasion.
            start = time.monotonic()
            hits, _ = Sweep(handle, deadline_seconds=45, concurrency=3).run(platforms=platforms)
            timings.append(time.monotonic() - start)
            by_platform = {hit["platform"]: hit for hit in hits}
            start = time.monotonic()
            baseline = {p["name"]: status_baseline(session, p, handle) for p in platforms}
            baseline_timings.append(time.monotonic() - start)
            for platform in platforms:
                hit = by_platform.get(platform["name"], {})
                rows.append({"username": handle, "platform": platform["name"],
                             "reference": truth[platform["name"]],
                             "myrecon": {"verdict": hit.get("verdict", "unknown"),
                                         "reason_code": hit.get("reason_code", "out_of_time"),
                                         "status_code": hit.get("status_code")},
                             "http200_baseline": baseline[platform["name"]]})
            print(f"Completed public control {len(timings)}/10", flush=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tools = {"myrecon": {**summarize(rows, "myrecon"), "p50_seconds": percentile(timings, .5), "p95_seconds": percentile(timings, .95)},
             "http200_baseline": {**summarize(rows, "http200_baseline"), "p50_seconds": percentile(baseline_timings, .5), "p95_seconds": percentile(baseline_timings, .95)}}
    metadata = {"myrecon": {"label": "MyRecon", "version": commit[:8], "commit": commit,
                            "status": "measured", "python_version": sys.version.split()[0],
                            "requests_version": requests.__version__, "max_connections": 3,
                            "connect_timeout_seconds": 6, "read_timeout_seconds": 8, "deadline_seconds": 45}}
    named_timings = {}
    for tool in NAMED_TOOLS:
        result = named_tool(tool, dataset, tool_python)
        metadata[tool] = result["metadata"]
        if require_named and metadata[tool]["status"] != "measured":
            raise RuntimeError(f"Pinned {tool} unavailable; retaining the previously published run")
        controls = {c["username"]: c for c in result["controls"]}
        for row in rows:
            row[tool] = controls[row["username"]]["checks"][row["platform"]]
        named_timings[tool] = [controls[h]["duration_seconds"] for h in handles]
        measured = [t for t in named_timings[tool] if t is not None]
        tools[tool] = {**summarize(rows, tool), "p50_seconds": percentile(measured, .5),
                       "p95_seconds": percentile(measured, .95)}
        print(f"Completed {tool}: {metadata[tool]['status']}", flush=True)
    username_timings = [dict(username=h, myrecon=round(a, 3), http200_baseline=round(b, 3),
                            **{tool: named_timings[tool][i] for tool in NAMED_TOOLS})
                        for i, (h, a, b) in enumerate(zip(handles, timings, baseline_timings))]
    harness_hash = hashlib.sha256()
    for name in ("daily_benchmark.py", "benchmark_worker.py", "benchmark-tools.json"):
        harness_hash.update(Path(__file__).with_name(name).read_bytes())
    return {"started_at_utc": started, "finished_at_utc": utc_now(), "version_or_commit": commit,
            "benchmark_harness_sha256": harness_hash.hexdigest(),
            "dataset_id": dataset["id"], "dataset_sha256": hashlib.sha256(json.dumps(dataset, sort_keys=True).encode()).hexdigest(),
            "username_count": len(handles), "platforms": dataset["platforms"], "cache_state": "application cache bypassed",
            "network_environment": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local workstation",
            "tools": tools, "tool_metadata": metadata,
            "username_timings_seconds": username_timings,
            "checks": rows}


def publish(run, output=OUTPUT, dataset=None):
    history = []
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        history = previous.get("runs", [])
    # A manual rerun replaces today's sample; never inflate history with repeats.
    day = run["started_at_utc"][:10]
    history = [r for r in history if r.get("started_at_utc", "")[:10] != day]
    history.append(run)
    history = sorted(history, key=lambda r: r["started_at_utc"])[-90:]
    next_due = datetime.fromisoformat(run["finished_at_utc"].replace("Z", "+00:00")) + timedelta(hours=24)
    document = {"schema_version": 2, "status": "measured", "updated_at_utc": run["finished_at_utc"],
                "next_update_due_utc": next_due.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "schedule": {"interval_hours": 24, "cron_utc": "17 3 * * *", "note": "Scheduled daily at 03:17 UTC. GitHub Actions can delay scheduled runs."},
                "dataset": dataset, "methodology": {
                    "scope": "10 fixed usernames across GitHub, GitLab and Hacker News: 30 username-platform checks, not the full catalogue.",
                    "reference": "Typed official API user objects or explicit absence. Failed, blocked and malformed responses have unknown truth and are excluded. The reference shares some API evidence with the production engine; this is a regression sample, not an independent identity or accuracy audit.",
                    "false_positive_rate": "FP / (FP + TN). Only reference negatives with definitive predictions count. Unknown negatives are reported separately.",
                    "accuracy": "(TP + TN) / (TP + TN + FP + FN). Read coverage alongside accuracy; unknowns and unscored reference checks are excluded.",
                    "baseline": "Real Sherlock and Maigret engines use their pinned bundled detection rules on the same ten usernames and three named platforms. HTTP 200 remains an optional status-only baseline, not a named tool. Older runs have no third-party measurements.",
                    "timing": "MyRecon, Sherlock and Maigret use up to three concurrent platform checks. MyRecon uses six-second connect/eight-second read timeouts and a 45-second sweep deadline; the named tools use an eight-second timeout. Tool-specific endpoints, headers and validation rules differ. Each tool runs in sequence on the same machine and network; startup/import time and reference checks are excluded. The HTTP baseline is sequential. Medians are descriptive, not a whole-catalogue speed ranking.",
                    "normalization": "Native Claimed maps to found, Available to not_found. Unsupported/disabled sites, native errors, missing outputs and known HTTP 401/403/429/5xx failures map to unknown. Native status is retained. No retries, recursion, enrichment, proxies, authentication or anti-block bypass. Per-tool code and site database fingerprints are recorded.",
                    "privacy": "Only these fixed public accounts and synthetic controls are benchmarked. No user search history is used or published.",
                    "limitations": "Small, fixed developer/community sample. It does not estimate whole-platform error rates or guarantee zero false positives."},
                "runs": history, "latest": run}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--tool-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--require-named-tools", action="store_true")
    args = parser.parse_args()
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    result = execute(dataset, args.tool_python, args.require_named_tools)
    publish(result, args.output, dataset)
    print(json.dumps(result["tools"], indent=2))
