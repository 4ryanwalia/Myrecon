"""
Network intelligence — Domain WHOIS, DNS, IP geolocation, reverse DNS.

Every lookup here uses a reliable, key-free public source:
  • WHOIS   → RDAP (rdap.org, the IANA-endorsed successor to WHOIS, JSON)
  • DNS     → DNS-over-HTTPS (Google / Cloudflare, JSON)
  • IP geo  → ip-api.com (free, no key)
  • rDNS    → socket.gethostbyaddr + DoH PTR fallback

These sources are stable and standardized, which is why these features are
accurate and low-maintenance compared with scraping.
"""

import socket
from typing import Optional

import requests

_UA = "MyRecon/1.0 (+https://myrecon.xyz)"
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}
_TIMEOUT = 10


# ══════════════════════════════════════════════════════════════════
#  DNS over HTTPS
# ══════════════════════════════════════════════════════════════════

_DOH_ENDPOINTS = [
    "https://dns.google/resolve",
    "https://cloudflare-dns.com/dns-query",
]
_DNS_RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA"]


def _doh_query(name: str, rtype: str) -> list[dict]:
    """Query a single record type via DNS-over-HTTPS, trying each endpoint."""
    for endpoint in _DOH_ENDPOINTS:
        try:
            headers = {"User-Agent": _UA, "Accept": "application/dns-json"}
            resp = requests.get(
                endpoint,
                params={"name": name, "type": rtype},
                headers=headers,
                timeout=_TIMEOUT,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            answers = data.get("Answer") or []
            records = []
            for ans in answers:
                # Only keep answers whose type matches what we asked for.
                if ans.get("type") == _DNS_TYPE_CODES.get(rtype):
                    records.append({
                        "value": ans.get("data", "").strip(),
                        "ttl": ans.get("TTL", 0),
                    })
            return records
        except Exception:
            continue
    return []


# Numeric DNS type codes so we can filter DoH answers precisely.
_DNS_TYPE_CODES = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "PTR": 12,
    "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257,
}


def dns_records(domain: str) -> dict:
    """Resolve the common record types for a domain."""
    records: dict[str, list[dict]] = {}
    for rtype in _DNS_RECORD_TYPES:
        found = _doh_query(domain, rtype)
        if found:
            records[rtype] = found

    total = sum(len(v) for v in records.values())
    return {
        "query": {"domain": domain},
        "summary": {"record_types": len(records), "total_records": total},
        "records": records,
    }


# ══════════════════════════════════════════════════════════════════
#  WHOIS via RDAP
# ══════════════════════════════════════════════════════════════════

def _rdap_entity_name(entities: list, role: str) -> str:
    """Extract a named entity (e.g. 'registrar') from RDAP vCard data."""
    for entity in entities or []:
        roles = entity.get("roles", [])
        if role in roles:
            vcard = entity.get("vcardArray", [])
            if len(vcard) > 1:
                for field in vcard[1]:
                    if field and field[0] == "fn":
                        return field[3]
            handle = entity.get("handle")
            if handle:
                return handle
    return ""


def whois_domain(domain: str) -> dict:
    """
    Fetch registration data for a domain using RDAP.

    Returns registrar, key dates, status flags, nameservers, and DNSSEC.
    """
    result = {
        "query": {"domain": domain},
        "found": False,
        "registrar": "",
        "created": "",
        "updated": "",
        "expires": "",
        "statuses": [],
        "nameservers": [],
        "dnssec": None,
        "contacts": {},
    }

    try:
        resp = requests.get(
            f"https://rdap.org/domain/{domain}",
            headers=_HEADERS,
            timeout=_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException:
        result["error"] = "WHOIS lookup failed — the RDAP service was unreachable."
        return result

    if resp.status_code == 404:
        result["message"] = "No registration record found (domain may be unregistered)."
        return result
    if resp.status_code != 200:
        result["error"] = f"WHOIS service returned status {resp.status_code}."
        return result

    try:
        data = resp.json()
    except ValueError:
        result["error"] = "WHOIS service returned an unreadable response."
        return result

    result["found"] = True
    result["registrar"] = _rdap_entity_name(data.get("entities", []), "registrar")

    # Events carry the registration lifecycle dates.
    for event in data.get("events", []):
        action = event.get("eventAction", "")
        date = event.get("eventDate", "")
        if action == "registration":
            result["created"] = date
        elif action in ("last changed", "last update of RDAP database"):
            result["updated"] = result["updated"] or date
        elif action == "expiration":
            result["expires"] = date

    result["statuses"] = data.get("status", [])

    for ns in data.get("nameservers", []):
        name = ns.get("ldhName") or ns.get("unicodeName")
        if name:
            result["nameservers"].append(name.lower())

    secure_dns = data.get("secureDNS") or {}
    if "delegationSigned" in secure_dns:
        result["dnssec"] = bool(secure_dns["delegationSigned"])

    registrant = _rdap_entity_name(data.get("entities", []), "registrant")
    if registrant:
        result["contacts"]["registrant"] = registrant

    return result


# ══════════════════════════════════════════════════════════════════
#  IP geolocation + reverse DNS
# ══════════════════════════════════════════════════════════════════

def reverse_dns(ip: str) -> Optional[str]:
    """Resolve an IP to a hostname (PTR record)."""
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return host
    except (socket.herror, socket.gaierror, OSError):
        # Fall back to DoH PTR lookup for robustness.
        try:
            reversed_name = _ptr_name(ip)
            records = _doh_query(reversed_name, "PTR")
            if records:
                return records[0]["value"].rstrip(".")
        except Exception:
            pass
    return None


def _ptr_name(ip: str) -> str:
    if ":" in ip:  # IPv6
        import ipaddress
        exploded = ipaddress.ip_address(ip).exploded.replace(":", "")
        return ".".join(reversed(exploded)) + ".ip6.arpa"
    return ".".join(reversed(ip.split("."))) + ".in-addr.arpa"


def ip_lookup(ip: str) -> dict:
    """
    Geolocate an IP and resolve its reverse DNS.

    Uses ip-api.com (free, no key). Server-side HTTP is acceptable here.
    """
    result = {
        "query": {"ip": ip},
        "found": False,
        "reverse_dns": reverse_dns(ip),
    }

    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={
                "fields": "status,message,continent,country,countryCode,"
                          "region,regionName,city,zip,lat,lon,timezone,isp,"
                          "org,as,asname,mobile,proxy,hosting,reverse,query"
            },
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        data = resp.json()
    except (requests.RequestException, ValueError):
        result["error"] = "IP geolocation service was unreachable."
        return result

    if data.get("status") != "success":
        result["error"] = data.get("message", "IP lookup failed.")
        return result

    result["found"] = True
    result["geo"] = {
        "continent": data.get("continent", ""),
        "country": data.get("country", ""),
        "country_code": data.get("countryCode", ""),
        "region": data.get("regionName", ""),
        "city": data.get("city", ""),
        "zip": data.get("zip", ""),
        "latitude": data.get("lat"),
        "longitude": data.get("lon"),
        "timezone": data.get("timezone", ""),
    }
    result["network"] = {
        "isp": data.get("isp", ""),
        "organization": data.get("org", ""),
        "asn": data.get("as", ""),
        "as_name": data.get("asname", ""),
    }
    result["flags"] = {
        "mobile": data.get("mobile", False),
        "proxy": data.get("proxy", False),
        "hosting": data.get("hosting", False),
    }
    if data.get("reverse") and not result.get("reverse_dns"):
        result["reverse_dns"] = data["reverse"]

    return result


# ══════════════════════════════════════════════════════════════════
#  Subdomain discovery via Certificate Transparency (crt.sh)
# ══════════════════════════════════════════════════════════════════

def _crtsh_subdomains(domain: str, suffix: str, found: set) -> None:
    """Collect subdomains from crt.sh Certificate Transparency search."""
    resp = requests.get(
        "https://crt.sh/",
        params={"q": f"%.{domain}", "output": "json", "exclude": "expired"},
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=20,
    )
    if resp.status_code == 200:
        for entry in resp.json():
            names = str(entry.get("name_value", "")).split("\n")
            cn = entry.get("common_name")
            if cn:
                names.append(cn)
            for name in names:
                name = name.strip().lower().lstrip("*.").rstrip(".")
                if name and "@" not in name and " " not in name \
                        and name != domain and name.endswith(suffix):
                    found.add(name)


def _certspotter_subdomains(domain: str, suffix: str, found: set) -> None:
    """Fallback CT source: Certspotter issuances API (free, no key)."""
    resp = requests.get(
        "https://api.certspotter.com/v1/issuances",
        params={"domain": domain, "include_subdomains": "true", "expand": "dns_names"},
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code == 200:
        for entry in resp.json():
            for name in entry.get("dns_names", []):
                name = str(name).strip().lower().lstrip("*.").rstrip(".")
                if name and "@" not in name and " " not in name \
                        and name != domain and name.endswith(suffix):
                    found.add(name)


def subdomains(domain: str, limit: int = 100) -> dict:
    """
    Discover subdomains from public Certificate Transparency logs.

    Every publicly-trusted TLS certificate is logged to CT, and the names on
    those certificates reveal subdomains — a reliable, passive source that
    needs no scanning or API key. Queries crt.sh first and falls back to
    Certspotter, so a slow or unavailable source doesn't lose the result.
    """
    domain = domain.lower().strip().strip(".")
    suffix = "." + domain
    found: set[str] = set()

    for source in (_crtsh_subdomains, _certspotter_subdomains):
        try:
            source(domain, suffix, found)
        except Exception:
            continue
        if found:
            break  # first source that returns data wins

    subs = sorted(found)
    return {
        "query": {"domain": domain},
        "source": "Certificate Transparency logs",
        "total": len(subs),
        "truncated": len(subs) > limit,
        "subdomains": subs[:limit],
    }


# ══════════════════════════════════════════════════════════════════
#  Combined domain intelligence
# ══════════════════════════════════════════════════════════════════

def domain_intel(domain: str) -> dict:
    """Aggregate WHOIS + DNS + resolved-IP geolocation for a domain."""
    whois = whois_domain(domain)
    dns = dns_records(domain)

    resolved_ips = [r["value"] for r in dns.get("records", {}).get("A", [])]
    ip_info = None
    if resolved_ips:
        ip_info = ip_lookup(resolved_ips[0])

    return {
        "query": {"domain": domain},
        "whois": whois,
        "dns": dns,
        "primary_ip": ip_info,
        "resolved_ips": resolved_ips,
    }
