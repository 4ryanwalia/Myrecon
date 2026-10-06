"""Secret-free, fixed-catalogue enumeration shared by Colab and Render.

The worker cannot choose URLs or access billing/Firebase. Wire results are
bounded and reconstructed against the server's catalogue before enrichment.
"""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from urllib.parse import urlsplit

from modules.sweep import Sweep, CATALOGUE, EXTENDED, REASONS, FOUND, NOT_FOUND, UNKNOWN
from modules.username_checker import UsernameChecker, PLATFORMS, STANDARD_LIMIT

PROTOCOL = 1


def catalogue(scope, deep=False):
    if scope == "standard":
        return [{"name": n, "url": u, "expected": e, "category": ""}
                for n, u, e in PLATFORMS[:STANDARD_LIMIT if deep else 50]]
    if scope not in ("full", "extended"):
        raise ValueError("Invalid scan scope")
    return EXTENDED if scope == "extended" else CATALOGUE


def fingerprint(scope, deep=False):
    digest = hashlib.sha256(json.dumps(catalogue(scope, deep), sort_keys=True).encode())
    root = Path(__file__).resolve().parents[1]
    for name in ("services/scan_engine.py", "modules/sweep.py", "modules/username_checker.py",
                 "modules/profile_identity.py", "core/netguard.py"):
        digest.update((root / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def _safe_image(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    parts = urlsplit(value)
    return value if parts.scheme in ("http", "https") and parts.hostname else None


def normalise(rows, username, scope, deep=False):
    if not isinstance(rows, list) or len(rows) > 32:
        raise ValueError("A checkpoint must contain at most 32 results")
    specs = {p["name"]: p for p in catalogue(scope, deep)}
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid checkpoint")
        name = row.get("platform")
        if name not in specs or name in seen:
            raise ValueError("Unknown or repeated platform")
        seen.add(name)
        p = specs[name]
        code = row.get("status_code", 0)
        if type(code) is not int or not -10 <= code <= 599:
            raise ValueError("Invalid HTTP status")
        url = p["url"].replace("{username}", username)
        if scope == "standard":
            exists = row.get("exists")
            score = row.get("match_score")
            if type(exists) is not bool or (score is not None and
                    (type(score) is not int or not -100 <= score <= 100)):
                raise ValueError("Invalid standard verdict")
            if exists and code != p["expected"]:
                raise ValueError("Contradictory standard verdict")
            clean = {"platform": name, "url": url, "status_code": code,
                     "exists": exists, "match_score": score,
                     "reason": str(row.get("reason", ""))[:240],
                     "confidence": row.get("confidence") if row.get("confidence") in
                         ("high", "medium", "low") else "low", "source": "username_check"}
            for field, limit in (("bio", 200), ("display_name", 100)):
                if isinstance(row.get(field), str):
                    clean[field] = row[field][:limit]
        else:
            verdict, reason = row.get("verdict"), row.get("reason_code")
            if verdict not in (FOUND, NOT_FOUND, UNKNOWN) or reason not in REASONS:
                raise ValueError("Invalid sweep verdict")
            label, unreachable = REASONS[reason]
            clean = {"platform": name, "platform_category": p["category"], "url": url,
                     "verdict": verdict, "exists": verdict == FOUND, "status_code": code,
                     "confidence": row.get("confidence") if row.get("confidence") in
                         ("high", "medium", "unverified") else "unverified",
                     "reason_code": reason, "reason": label,
                     "unreachable": unreachable if verdict == UNKNOWN else False,
                     "source": "username_sweep", "username": username,
                     "display_name": str(row.get("display_name") or "")[:100] or None}
        clean["profile_pic_url"] = _safe_image(row.get("profile_pic_url"))
        out.append(clean)
    return out


def coverage(rows, total):
    return {"total": total, "found": sum(r["verdict"] == FOUND for r in rows),
            "not_found": sum(r["verdict"] == NOT_FOUND for r in rows),
            "undetermined": sum(r["verdict"] == UNKNOWN and not r["unreachable"] for r in rows),
            "unreachable": sum(r["verdict"] == UNKNOWN and r["unreachable"] for r in rows),
            "unchecked": sum(r.get("reason_code") == "out_of_time" for r in rows)}


def enumerate_batches(username, scope, deep=False, completed=(), concurrency=8,
                      deadline_seconds=300, cancelled=lambda: False):
    """Bound the active futures; empty batches are lease-renewal opportunities."""
    specs = catalogue(scope, deep)
    todo = iter(p for p in specs if p["name"] not in set(completed))
    concurrency = max(1, min(32, concurrency))
    end = time.monotonic() + deadline_seconds
    sweep = Sweep(username, deadline_seconds=deadline_seconds, concurrency=concurrency)
    checker = UsernameChecker(max_workers=concurrency, delay=0)

    def probe(p):
        if scope == "standard":
            return checker._check_platform(p["name"], p["url"].replace("{username}", username),
                                           p["expected"], username)
        try:
            return sweep.probe(p)
        except Exception:
            return sweep._hit(p, UNKNOWN, p["url"].replace("{username}", username),
                              0, "unverified", "transport")

    pending, recorded, exhausted = {}, set(completed), False
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            while pending or not exhausted:
                if cancelled():
                    sweep.stop()
                    break
                if time.monotonic() >= end:
                    sweep.stop()
                    break
                while not exhausted and len(pending) < concurrency:
                    p = next(todo, None)
                    if p is None:
                        exhausted = True
                    else:
                        pending[pool.submit(probe, p)] = p
                if not pending:
                    break
                done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                batch = []
                for future in done:
                    p = pending.pop(future)
                    recorded.add(p["name"])
                    batch.append(future.result())
                yield batch
            for future in pending:
                future.cancel()
        if not cancelled():
            for p in specs:
                if p["name"] in recorded:
                    continue
                if scope == "standard":
                    yield [{"platform": p["name"], "exists": False, "status_code": -1,
                            "match_score": None, "reason": "not checked before the scan deadline"}]
                else:
                    yield [sweep._hit(p, UNKNOWN, p["url"].replace("{username}", username),
                                     0, "unverified", "out_of_time")]
    finally:
        sweep.stop()
        sweep.session.close()
