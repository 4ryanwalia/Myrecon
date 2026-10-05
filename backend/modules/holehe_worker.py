"""Separate optional runtime. No CLI updater, progress output or recovery data."""
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import ssl
import sys
from urllib.parse import parse_qsl, urlsplit

CATALOG = json.loads((Path(__file__).resolve().parents[1] / "data" / "email-account-services.json").read_text(encoding="utf-8"))


def normalize(raw, row, blocked=False, failed=False):
    status, reason = "unavailable", "No readable registration answer"
    if blocked:
        status, reason = "skipped", "Request could create an account, attempt a password, or send a recovery message"
    elif not failed and isinstance(raw, dict):
        if raw.get("rateLimit") is True:
            status, reason = "rate_limited", "Provider blocked or rate-limited this check"
        elif raw.get("error"):
            pass
        elif raw.get("exists") is True:
            status, reason = "found", "Service returned an email-registration signal; no profile or ownership verified"
        elif raw.get("exists") is False:
            status, reason = "no_signal", "No registration signal returned; this does not prove no account"
    return {"service": row["name"], "id": row["id"], "domain": row["domain"],
            "method": row["method"], "status": status, "reason": reason}


def request_allowed(request):
    url = urlsplit(str(request.url))
    if url.scheme != "https":
        return False
    if re.search(r"reset|recover|forgot|send.?email|send.?code|send.?otp", url.path, re.I):
        return False
    # Checks may submit email-validation forms. Never submit credentials,
    # create an account with a password, or perform a login attempt.
    payload = request.content.decode("utf-8", errors="ignore")
    fields = dict(parse_qsl(payload))
    try:
        decoded = json.loads(payload)
        if isinstance(decoded, dict): fields.update(decoded)
    except ValueError:
        pass
    fields.update(dict(parse_qsl(url.query)))
    def flatten(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key, item
                yield from flatten(item)
        elif isinstance(value, list):
            for item in value: yield from flatten(item)
    fields = dict(flatten(fields))
    if any(re.search(r"pass(word|wd)?|secret|otp", str(key), re.I) and value
           for key, value in fields.items()):
        return False
    if any(re.search(r"send.?email|send.?code|send.?otp", str(key), re.I) and value
           for key, value in fields.items()):
        return False
    return request.method in ("GET", "POST", "HEAD")


async def run(email, httpx, trio, checkpoint=None):
    rows = [{"service": r["name"], "id": r["id"], "domain": r["domain"], "method": r["method"],
             "status": "timeout" if r["enabled"] else "skipped",
             "reason": "Scan time budget reached" if r["enabled"] else r["skip_reason"]}
            for r in CATALOG["services"]]
    limiter = trio.CapacityLimiter(12)
    # Loading the CA store for every client monopolises CPU on small hosts.
    # Keep cookies/sessions isolated, but reuse the immutable TLS trust setup.
    tls_context = ssl.create_default_context()
    finished = 0

    def save_progress():
        nonlocal finished
        finished += 1
        if checkpoint and finished % 12 == 0:
            checkpoint(rows)

    async def check(index, row):
        if not row["enabled"]: return
        async with limiter:
            blocked, failed, throttled = False, False, False
            calls = 0
            out = []
            async def before(request):
                nonlocal blocked, calls
                calls += 1
                if calls > 5 or not request_allowed(request):
                    blocked = True
                    raise httpx.RequestError("Request excluded", request=request)
            async def after(response):
                nonlocal failed, throttled
                if response.status_code in (403, 429): throttled = True
                elif response.status_code >= 500: failed = True
            try:
                module = importlib.import_module(row["module"])
                if hashlib.sha256(Path(module.__file__).read_text(encoding="utf-8").encode("utf-8")).hexdigest() != row["sha256"]:
                    rows[index] = normalize(None, row)
                    rows[index]["reason"] = "Module differs from reviewed version"
                    return
                with trio.move_on_after(7) as timeout:
                    async with httpx.AsyncClient(timeout=4, follow_redirects=False, verify=tls_context,
                                                  event_hooks={"request": [before], "response": [after]}) as client:
                        await getattr(module, row["id"])(email, client, out)
                if timeout.cancelled_caught:
                    rows[index]["reason"] = "Service time budget reached"
                    return
                raw = out[-1] if out else None
                if throttled: raw = {"rateLimit": True}
                rows[index] = normalize(raw, row, blocked=blocked, failed=failed)
            except Exception:
                rows[index] = normalize(None, row, blocked=blocked)
            finally:
                save_progress()

    with trio.move_on_after(35):
        async with trio.open_nursery() as nursery:
            # Prioritise requested mainstream services within the scan budget.
            order = sorted(enumerate(CATALOG["services"]), key=lambda pair:
                           pair[1]["id"] not in {"spotify", "github", "instagram", "twitter", "pinterest", "soundcloud", "amazon", "patreon"})
            for index, row in order: nursery.start_soon(check, index, row)
    return rows


def main():
    payload = json.loads(sys.stdin.read(1024))
    email = payload.get("email", "")
    if not re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email):
        raise ValueError("Invalid email")
    try:
        import httpx
        import trio
        output = sys.stdout
        def checkpoint(rows):
            print(json.dumps({"status": "partial", "services": rows}), file=output, flush=True)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rows = trio.run(run, email, httpx, trio, checkpoint)
        print(json.dumps({"status": "ok", "services": rows}))
    except ImportError:
        print(json.dumps({"status": "unavailable", "services": [
            {"service": r["name"], "id": r["id"], "domain": r["domain"], "method": r["method"],
             "status": "unavailable" if r["enabled"] else "skipped",
             "reason": "Holehe runtime not installed" if r["enabled"] else r["skip_reason"]}
            for r in CATALOG["services"]]}))


if __name__ == "__main__": main()
