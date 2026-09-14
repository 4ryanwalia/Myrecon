"""
Argument parsing and dispatch for the MyRecon terminal client.

Each subcommand is a thin shell around the same `backend/services` function the
matching Flask route calls, so there is one implementation of every lookup and
the CLI cannot answer differently from myrecon.xyz.

Two commands exist here that the web API has no route for, because they only
make sense with a filesystem and a shell:

    forensics   read a local image file's own bytes (EXIF, GPS, hashes)
    geo         resolve coordinates — including ones `forensics` just found

Exit codes: 0 success, 1 a lookup failed, 2 bad input, 130 interrupted.
"""

from __future__ import annotations

import argparse
import os
import sys

__version__ = "1.0.0"

# The backend package uses absolute imports (`from services...`, `from
# modules...`), so its directory has to be importable as a root, not as a
# `backend.` package. Adding it here keeps those modules unmodified.
_CLI_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_CLI_DIR)
_BACKEND = os.path.join(_ROOT, "backend")

for _path in (_BACKEND, _ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from cli import ui, views  # noqa: E402 - must follow the sys.path setup above


EPILOG = """\
examples:
  myrecon username torvalds --deep
  myrecon email someone@example.com
  myrecon domain example.com
  myrecon investigate torvalds
  myrecon forensics ./photo.jpg
  myrecon username torvalds --json > scan.json

Every source is free and keyless except `name` and `image`, which need a
Google Custom Search key (GOOGLE_API_KEY and GOOGLE_CX_ID) on the machine
running the scan. `forensics` needs Pillow and numpy: pip install Pillow numpy
"""


# ── Scan helpers ─────────────────────────────────────────────────

def _progress_for(args) -> "ui.Progress":
    return ui.Progress(enabled=not args.quiet)


def _scan_username(handle: str, deep: bool, progress) -> dict:
    """Stream when there is someone watching, plain call when there is not."""
    if not progress.enabled:
        from services.search import search_username
        return search_username(handle, deep)

    from services.search import stream_username

    data = None
    for event in stream_username(handle, deep):
        kind = event.get("type")
        if kind == "complete":
            data = event.get("data")
        elif kind == "error":
            progress.clear()
            raise RuntimeError(event.get("error") or "Scan failed.")
        else:
            progress.update(event)
    progress.clear()
    if data is None:
        raise RuntimeError("Scan produced no result.")
    return data


# ── Commands ─────────────────────────────────────────────────────

def _cmd_username(args) -> tuple:
    from core import validation

    handle = validation.username(args.username)
    data = _scan_username(handle, args.deep, _progress_for(args))
    return data, lambda d: views.username_report(d, args.all)


def _cmd_name(args) -> tuple:
    from core import validation
    from services.search import search_fullname

    name = validation.full_name(args.full_name)
    data = search_fullname(name, args.deep)
    return data, lambda d: views.fullname_report(d, args.all)


def _cmd_email(args) -> tuple:
    from core import validation
    from services.email import scan_email

    address = validation.email(args.email)
    return scan_email(address), views.email_report


def _cmd_domain(args) -> tuple:
    from core import validation
    from services.network import scan_domain

    return scan_domain(validation.domain(args.domain)), views.domain_report


def _cmd_dns(args) -> tuple:
    from core import validation
    from services.network import scan_dns

    return scan_dns(validation.domain(args.domain)), views.dns_report


def _cmd_whois(args) -> tuple:
    from core import validation
    from services.network import scan_whois

    return scan_whois(validation.domain(args.domain)), views.whois_report


def _cmd_ip(args) -> tuple:
    from core import validation
    from services.network import scan_ip

    return scan_ip(validation.ip_address(args.ip)), views.ip_report


def _cmd_subdomains(args) -> tuple:
    from core import validation
    from services.network import scan_subdomains

    data = scan_subdomains(validation.domain(args.domain))
    return data, lambda d: views.subdomains_report(d, args.all)


def _cmd_enrich(args) -> tuple:
    from core import validation
    from services.enrich import enrich_profile

    platform = validation.platform_name(args.platform)
    handle = validation.username(args.username)
    return enrich_profile(platform, handle), views.enrich_report


def _cmd_wayback(args) -> tuple:
    from core import validation
    from modules.wayback import history

    url = validation.page_url(args.url)
    return history(url), lambda d: views.wayback_report(d, url)


def _cmd_image(args) -> tuple:
    from core import validation
    from services.image import scan_image

    url = validation.image_url(args.url)
    data = scan_image(url, args.deep)
    return data, lambda d: views.image_report(d, args.all)


def _cmd_investigate(args) -> tuple:
    from core import validation
    from services.investigation import investigate

    handle = validation.username(args.handle)
    progress = _progress_for(args)
    data = investigate(handle, deep=args.deep, emit=progress.update)
    progress.clear()
    return data, views.investigate_report


def _cmd_forensics(args) -> tuple:
    """Local image analysis — the one command that reads from disk."""
    path = args.path
    if not os.path.isfile(path):
        raise FileNotFoundError("No such file: " + path)

    try:
        from modules.image_forensics import ImageForensicsError, analyse
    except ImportError as exc:
        raise RuntimeError(
            "Image forensics needs Pillow and numpy, which the API does not "
            "install by default.  pip install Pillow numpy  (" + str(exc) + ")"
        ) from exc

    with open(path, "rb") as handle:
        raw = handle.read()

    try:
        data = analyse(raw, filename=os.path.basename(path))
    except ImageForensicsError as exc:
        raise ValueError(str(exc)) from exc
    return data, views.forensics_report


def _cmd_geo(args) -> tuple:
    from modules.geo_intel import investigate_location

    data = investigate_location(args.lat, args.lon, radius_m=args.radius)
    return data, views.geo_report


def _cmd_platforms(args) -> tuple:
    from modules.username_checker import PLATFORMS

    names = sorted(entry[0] for entry in PLATFORMS)
    data = {"status": "ok", "total": len(names), "platforms": names}

    def render(payload: dict) -> None:
        ui.heading("Platforms checked", str(payload["total"]) + " in the sweep")
        names = payload["platforms"]
        cell = max((len(n) for n in names), default=10) + 2
        per_row = max(1, (ui.width() - 4) // cell)
        for start in range(0, len(names), per_row):
            ui.line("".join(n.ljust(cell) for n in names[start:start + per_row]).rstrip(),
                    indent=4)

    return data, render


def _cmd_serve(args) -> tuple:
    """Run the API locally — the same entry point `backend/dev.py` uses."""
    os.environ.setdefault("FLASK_ENV", "development")
    from app import app

    ui.success("API on http://" + args.host + ":" + str(args.port) +
               "  (health: /api/health)")
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return None, None


# ── Parser ───────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        help="print the raw service result instead of a report")
    common.add_argument("--quiet", "-q", action="store_true",
                        help="no progress line")
    common.add_argument("--color", choices=("auto", "always", "never"),
                        default="auto", help="colour output (default: auto)")

    parser = argparse.ArgumentParser(
        prog="myrecon",
        description="MyRecon — OSINT lookups from the terminal, same engine as myrecon.xyz.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version",
                        version="myrecon " + __version__)
    subs = parser.add_subparsers(dest="command", metavar="<command>")

    def add(name: str, help_text: str):
        return subs.add_parser(name, parents=[common], help=help_text,
                               description=help_text)

    p = add("username", "Sweep 100+ platforms for a handle, then enrich and correlate.")
    p.add_argument("username")
    p.add_argument("--deep", action="store_true", help="wider sweep, slower")
    p.add_argument("--all", action="store_true", help="show every row, including rejections")
    p.set_defaults(func=_cmd_username)

    p = add("name", "Search a full name across the web (needs a Google CSE key).")
    p.add_argument("full_name")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=_cmd_name)

    p = add("email", "Breach exposure, Gravatar, GitHub and address analysis.")
    p.add_argument("email")
    p.set_defaults(func=_cmd_email)

    p = add("domain", "Registration, DNS and hosting for a domain, in one report.")
    p.add_argument("domain")
    p.set_defaults(func=_cmd_domain)

    p = add("dns", "DNS records over DNS-over-HTTPS.")
    p.add_argument("domain")
    p.set_defaults(func=_cmd_dns)

    p = add("whois", "Registration record via RDAP, falling back to WHOIS.")
    p.add_argument("domain")
    p.set_defaults(func=_cmd_whois)

    p = add("ip", "Geolocation, ASN, reverse DNS and proxy/hosting flags.")
    p.add_argument("ip")
    p.set_defaults(func=_cmd_ip)

    p = add("subdomains", "Subdomains from Certificate Transparency logs.")
    p.add_argument("domain")
    p.add_argument("--all", action="store_true", help="list every subdomain found")
    p.set_defaults(func=_cmd_subdomains)

    p = add("enrich", "Fetch one profile's details from one platform.")
    p.add_argument("platform", help="platform name, e.g. Instagram (see `platforms`)")
    p.add_argument("username")
    p.set_defaults(func=_cmd_enrich)

    p = add("wayback", "How long a URL has been archived, and the latest capture.")
    p.add_argument("url")
    p.set_defaults(func=_cmd_wayback)

    p = add("image", "Reverse image search by URL (needs a Google CSE key).")
    p.add_argument("url")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=_cmd_image)

    p = add("forensics", "Analyse a local image file: EXIF, GPS, hashes, provenance.")
    p.add_argument("path", help="path to an image on this machine")
    p.set_defaults(func=_cmd_forensics)

    p = add("geo", "Resolve GPS coordinates to a place, keyless.")
    p.add_argument("lat", type=float)
    p.add_argument("lon", type=float)
    p.add_argument("--radius", type=int, default=1000,
                   help="metres to search for notable places (default: 1000)")
    p.set_defaults(func=_cmd_geo)

    p = add("investigate", "Build an entity graph for a handle and assess it.")
    p.add_argument("handle")
    p.add_argument("--deep", action="store_true")
    p.set_defaults(func=_cmd_investigate)

    p = add("platforms", "List every platform the username sweep checks.")
    p.set_defaults(func=_cmd_platforms)

    p = add("serve", "Run the MyRecon API on this machine.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    p.set_defaults(func=_cmd_serve)

    return parser


# ── Entry point ──────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        ui.configure("auto")
        ui.banner("Same engine as myrecon.xyz, no server required.")
        parser.print_help()
        return 0

    ui.configure(args.color)

    try:
        data, render = args.func(args)
    except KeyboardInterrupt:
        ui.error("Interrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001 - every failure is reported, never raised
        from core.validation import ValidationError

        if isinstance(exc, (ValidationError, ValueError, FileNotFoundError)):
            ui.error(str(exc))
            return 2
        ui.error(type(exc).__name__ + ": " + str(exc))
        return 1

    if data is None:  # `serve` renders nothing; it blocks and then exits
        return 0

    if data.get("status") == "error" or data.get("error"):
        message = data.get("error") or "The lookup failed."
        if args.json:
            ui.dump_json(data)
        else:
            ui.error(str(message))
        return 1

    if args.json:
        ui.dump_json(data)
    else:
        render(data)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
