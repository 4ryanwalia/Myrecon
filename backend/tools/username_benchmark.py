"""Opt-in public username case study. Kept separate from daily controls.

Run --username USER --output-dir DIR with the pinned benchmark Python.
Only verdicts, public profile links, timings and rule provenance are retained.
Each completed tool is checkpointed so a later failure cannot erase evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from daily_benchmark import ROOT, utc_now
from modules.sweep import CATALOGUE, Sweep, CONCURRENCY, DEADLINE_SECONDS


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(username, output_dir, tool):
    started = utc_now()
    if tool == "myrecon":
        before = time.monotonic()
        def progress(hit, checked, total):
            if checked % 50 == 0 or checked == total:
                print(f"MyRecon {checked}/{total}", flush=True)
        hits, coverage = Sweep(username).run(on_result=progress)
        duration = round(time.monotonic() - before, 3)
        data = {"metadata": {"label": "MyRecon", "status": "measured",
            "scope": "standard full catalogue", "catalogue_entries": len(CATALOGUE),
            "max_connections": CONCURRENCY, "deadline_seconds": DEADLINE_SECONDS,
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "engine_sha256": hashlib.sha256((ROOT / "backend/modules/sweep.py").read_bytes()).hexdigest(),
            "profile_identity_sha256": hashlib.sha256((ROOT / "backend/modules/profile_identity.py").read_bytes()).hexdigest(),
            "site_database_sha256": hashlib.sha256(json.dumps(CATALOGUE, sort_keys=True).encode()).hexdigest()},
            "controls": [{"username": username, "duration_seconds": duration,
                "checks": {h["platform"]: {k: h[k] for k in
                    ("verdict", "url", "status_code", "confidence", "reason_code")} for h in hits}}]}
    else:
        dataset = output_dir / "input.json"
        write(dataset, {"usernames": [username], "platforms": []})
        result = output_dir / f"{tool}.json"
        subprocess.run([sys.executable, str(Path(__file__).with_name("benchmark_worker.py")),
            "--tool", tool, "--dataset", str(dataset), "--output", str(result), "--full"],
            check=True, timeout=3600)
        data = json.loads(result.read_text(encoding="utf-8"))
    data.update(started_at_utc=started, finished_at_utc=utc_now(), network_environment="local workstation",
                cache_state="application cache bypassed", username=username)
    write(output_dir / f"{tool}.json", data)
    checks = data["controls"][0]["checks"]
    print(json.dumps({"tool": tool, "checked": len(checks), "counts": {
        v: sum(c["verdict"] == v for c in checks.values()) for v in ("found", "not_found", "unknown")}}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tool", choices=("myrecon", "sherlock", "maigret", "all"), default="all")
    args = parser.parse_args()
    if not args.username.isascii() or not all(c.isalnum() or c in "._-" for c in args.username):
        parser.error("Use a single plain username")
    for tool in ("myrecon", "sherlock", "maigret") if args.tool == "all" else (args.tool,):
        run(args.username, args.output_dir, tool)
