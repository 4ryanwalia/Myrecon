"""Build the public case study from checkpointed runs and source reviews."""
import argparse
import json
from pathlib import Path

from review_username_benchmark import address
from username_benchmark import write

TOOLS = ("myrecon", "sherlock", "maigret")


def reported(check):
    return check.get("native_status") == "CLAIMED" if "native_status" in check else check["verdict"] == "found"


def summarize(checks, reviews, allowed=None):
    selected = [c for c in checks if allowed is None or c["address"] in allowed]
    hits = [c for c in selected if c["reported"]]
    unique = {c["address"] for c in hits if c["address"]}
    labels = [reviews.get(key, {}).get("verdict", "unknown") for key in unique]
    grouped = {}
    for check in selected:
        grouped.setdefault(check["address"], []).append(check)
    return {"checked": len(selected) if allowed is None else len(grouped), "raw_checks": len(selected), "reported": len(hits), "unique_reported": len(unique),
        "duplicates": len(hits) - len(unique), "source_supported": labels.count("found"),
        "source_contradicted": labels.count("not_found"), "unverified": labels.count("unknown"),
        "unknown_predictions": sum(c["verdict"] == "unknown" for c in selected) if allowed is None
            else sum(all(c["verdict"] == "unknown" for c in group) for group in grouped.values())}


def build(folder, output):
    reviews = json.loads((folder / "source-reviews.json").read_text(encoding="utf-8"))
    tools, by_address = {}, {}
    username = None
    for tool in TOOLS:
        run = json.loads((folder / f"{tool}.json").read_text(encoding="utf-8"))
        if username is None:
            username = run["username"]
        if run["username"] != username or run["controls"][0]["username"] != username or run["metadata"]["status"] != "measured":
            raise ValueError("Case-study runs must measure the same username")
        checks = []
        for platform, check in run["controls"][0]["checks"].items():
            key = address(check["url"]) if check.get("url") else ""
            row = {"platform": platform, **check, "address": key, "reported": reported(check)}
            checks.append(row)
            if key:
                by_address.setdefault(key, {})[tool] = row
        tools[tool] = {"metadata": run["metadata"], "started_at_utc": run["started_at_utc"],
            "finished_at_utc": run["finished_at_utc"], "duration_seconds": run["controls"][0]["duration_seconds"],
            "checks": checks, "summary": summarize(checks, reviews)}
    shared = {key for key, checks in by_address.items() if all(t in checks for t in TOOLS)}
    for tool in TOOLS:
        tools[tool]["shared_summary"] = summarize(tools[tool]["checks"], reviews, shared)
    # The public preview exposes platform names, not profile URLs or all checks.
    # It cannot be included in the exact-profile-address intersection.
    preview = json.loads((folder / "osintsearch.json").read_text(encoding="utf-8"))
    if preview.get("username") != username:
        raise ValueError("The recorded preview must match the measured username")
    tools["osintsearch"] = preview
    rows = [{"address": key, "shared": key in shared, "tools": checks,
             "reference": reviews.get(key, {"verdict": "unknown", "evidence": "unreviewed"})}
            for key, checks in sorted(by_address.items()) if any(c["reported"] for c in checks.values())]
    diagnostic = json.loads((folder / "sherlock-bundled-diagnostic.json").read_text())
    diagnostic_checks = [{**c, "address": address(c["url"]) if c.get("url") else "", "reported": reported(c)}
                         for c in diagnostic["controls"][0]["checks"].values()]
    before = json.loads((folder / "myrecon-before-fix.json").read_text())
    before_checks = [{**c, "address": address(c["url"]), "reported": reported(c)}
                     for c in before["controls"][0]["checks"].values()]
    recovery = None
    recovery_path = folder / "myrecon-before-recovery.json"
    if recovery_path.exists():
        old = json.loads(recovery_path.read_text())
        if old["username"] != username or old["controls"][0]["username"] != username:
            raise ValueError("The pre-recovery run must match the measured username")
        old_checks = [{**c, "address": address(c["url"]), "reported": reported(c)}
                      for c in old["controls"][0]["checks"].values()]
        old_reported = {c["address"] for c in old_checks if c["reported"]}
        recovered = [c["platform"] for c in tools["myrecon"]["checks"] if c["reported"]
                     and c["address"] not in old_reported and reviews.get(c["address"], {}).get("verdict") == "found"]
        recovery = {"summary": summarize(old_checks, reviews), "started_at_utc": old["started_at_utc"],
                    "recovered_source_supported": recovered,
                    "note": "Exact creator data and OpenStreetMap profile identities were added, and Reddit now requires a typed account object. All are general rules, not saved results for this username. Blocks remain unknown; counts may change between runs."}
    data = {"schema_version": 1, "username": run["username"],
        "tools": tools, "shared_address_count": len(shared), "results": rows,
        "sherlock_bundled_diagnostic": {"summary": summarize(diagnostic_checks, reviews),
            "excluded_reported": sum(reported(c) for name, c in diagnostic["controls"][0]["checks"].items()
                                     if name in tools["sherlock"]["metadata"]["excluded_sites"]),
            "note": "Diagnostic run without upstream exclusions. The main Sherlock comparison honors its current exclusions."},
        "myrecon_before_fix": {"summary": summarize(before_checks, reviews),
            "note": "Initial run included RubyGems' fermion profile. The exact-handle check was fixed and MyRecon rerun."},
        "myrecon_before_recovery": recovery,
        "methodology": {
            "scope": "One owner-requested public username. MyRecon standard full catalogue, Sherlock full bundled catalogue with current upstream exclusions, Maigret enabled unprotected username catalogue, and OSINTsearch free preview.",
            "shared": "Intersection of exact public profile addresses across the three local engines, normalized only for www, trailing slashes and the known Buy Me a Coffee redirect. Counts reuse those checks from the full runs. Different schemes or endpoint paths are not assumed equivalent. OSINTsearch hides profile URLs and is excluded from this intersection.",
            "reference": "Independent source observations and separately recorded manual evidence. Official API account objects confirm existence. Explicit missing responses or a different account handle contradict a reported exact-handle result. HTTP 200, agreement between tools, a challenge or a login wall does not confirm an account. Ownership is not inferred.",
            "noise": "Reported hits include native CLAIMED outcomes even when normalization quarantines an HTTP error. Each unique address is source-supported, source-contradicted or unverified; duplicate addresses are shown separately. Unverified is not a false-positive label. Source-contradicted counts are observed lower bounds, not a whole-catalogue rate.",
            "timing": "Tools ran on the same workstation. Some runs overlapped. Counts and source evidence are compared; timings are descriptive and not a speed ranking.",
            "limitations": "One username is a case study, not an overall accuracy ranking or zero-error guarantee. Platform responses can change between the tool run and verification. OSINTsearch exposes 14 of 19 grouped matches; five unnamed matches and all profile links are hidden. No assumptions are made about those hidden results.",
            "privacy": "This username was explicitly supplied for this comparison. Customer history, credentials, private content and breach data are not used."}}
    write(output, data)
    print(json.dumps({t: d.get("summary") for t, d in tools.items()}, indent=2))
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.input_dir, args.output)
