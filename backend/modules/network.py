"""
Network intelligence, Domain WHOIS, DNS, IP geolocation, reverse DNS.

Every lookup here uses a reliable, key-free public source:
  • WHOIS   → RDAP (rdap.org, the IANA-endorsed successor to WHOIS, JSON)
  • DNS     → DNS-over-HTTPS (Google / Cloudflare, JSON)
  • IP geo  → ip-api.com (free, no key)
  • rDNS    → socket.gethostbyaddr + DoH PTR fallback

These sources are stable and standardized, which is why these features are
accurate and low-maintenance compared with scraping.
"""

import re
import socket
from concurrent.futures import ThreadPoolExecutor
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
    """Resolve the common record types for a domain, plus its mail posture."""
    # In parallel: one at a time, eight lookups with a 10s timeout and a
    # fallback resolver each could hold a request for well over a minute.
    with ThreadPoolExecutor(max_workers=len(_DNS_RECORD_TYPES) + 1) as pool:
        futures = {rtype: pool.submit(_doh_query, domain, rtype) for rtype in _DNS_RECORD_TYPES}
        dmarc_future = pool.submit(_dmarc_lookup, domain)
        records: dict[str, list[dict]] = {}
        for rtype, future in futures.items():
            found = future.result()
            if found:
                records[rtype] = found
        dmarc = dmarc_future.result()

    total = sum(len(v) for v in records.values())
    return {
        "query": {"domain": domain},
        "summary": {"record_types": len(records), "total_records": total},
        "records": records,
        "mail_security": mail_security(records.get("TXT", []), dmarc),
    }


# ══════════════════════════════════════════════════════════════════
#  Mail spoofing protection (SPF + DMARC)
# ══════════════════════════════════════════════════════════════════
#
# Answers the question the raw records don't: can someone send mail that
# claims to come from this domain and have it delivered? DKIM is left out on
# purpose, its key lives at <selector>._domainkey.<domain>, and the selector
# is only known to whoever sends the mail, so it cannot be checked from here.

def _txt_value(raw: str) -> str:
    """Join a TXT answer's quoted strings. Resolvers differ on quoting, and a
    long SPF record arrives as several strings that must be concatenated."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', raw or "")
    return "".join(parts) if parts else (raw or "").strip()


def _dmarc_lookup(domain: str) -> dict:
    """Find the DMARC record for a domain, walking up to its parent domains.

    A subdomain without its own record is covered by the organisational
    domain's, under that record's sp= policy when it sets one.
    """
    labels = domain.split(".")
    for i in range(0, max(1, len(labels) - 1)):
        name = ".".join(labels[i:])
        found = [_txt_value(r["value"]) for r in _doh_query(f"_dmarc.{name}", "TXT")]
        found = [v for v in found if v.lower().startswith("v=dmarc1")]
        if found:
            return {"name": name, "records": found, "inherited": i > 0}
        if i >= 3:
            break
    return {"name": domain, "records": [], "inherited": False}


def _dmarc_tags(record: str) -> dict:
    tags = {}
    for part in record.split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            tags[key.strip().lower()] = value.strip()
    return tags


def mail_security(txt_records: list, dmarc: dict) -> dict:
    """Grade how well a domain's SPF and DMARC stop forged mail.

    Verdicts, strongest first:
      protected, DMARC tells receivers to quarantine or reject all forged mail
      partial, records exist, but nothing makes a receiver act on every failure
      exposed, no DMARC and no usable SPF, or SPF that authorises anyone

    DMARC decides it. Forged mail can pass neither SPF nor DKIM for a domain it
    does not control, so an enforcing policy stops it whatever SPF says, and
    SPF alone checks the envelope sender, not the From address a person sees.
    """
    spf_values = [v for v in (_txt_value(r.get("value", "")) for r in txt_records)
                  if v.lower().startswith("v=spf1")]
    spf = {"present": bool(spf_values), "record": spf_values[0] if spf_values else "",
           "all": None, "redirect": False, "valid": len(spf_values) == 1}
    if spf_values:
        m = re.search(r"(?:^|\s)([+~?-]?)all(?:\s|$)", spf_values[0], re.I)
        if m:
            spf["all"] = (m.group(1) or "+") + "all"
        # redirect= hands evaluation to another record, which carries the all.
        spf["redirect"] = bool(re.search(r"(?:^|\s)redirect=", spf_values[0], re.I))

    dmarc_values = dmarc.get("records") or []
    dm = {"present": bool(dmarc_values), "record": dmarc_values[0] if dmarc_values else "",
          "policy": None, "pct": 100, "reports": False, "valid": len(dmarc_values) == 1,
          "checked": f"_dmarc.{dmarc.get('name', '')}", "inherited": bool(dmarc.get("inherited"))}
    if dmarc_values:
        tags = _dmarc_tags(dmarc_values[0])
        policy = tags.get("sp") if dm["inherited"] and tags.get("sp") else tags.get("p")
        dm["policy"] = (policy or "").lower() or None
        try:
            dm["pct"] = max(0, min(100, int(tags.get("pct", "100"))))
        except ValueError:
            pass
        dm["reports"] = bool(tags.get("rua"))

    issues = []
    if len(spf_values) > 1:
        issues.append("More than one SPF record is published, which makes SPF fail for every message.")
    if spf["all"] == "+all":
        issues.append("SPF ends in +all, which authorises every server on the internet to send as this domain.")
    if spf["present"] and spf["all"] is None and not spf["redirect"]:
        issues.append("SPF has no closing all mechanism, so mail from unlisted servers is not marked as failing.")
    if len(dmarc_values) > 1:
        issues.append("More than one DMARC record is published, so receivers ignore DMARC entirely.")
    if dm["present"] and dm["policy"] == "none":
        issues.append("DMARC policy is p=none: failures are reported, but forged mail is still delivered.")
    if dm["present"] and dm["policy"] in ("quarantine", "reject") and dm["pct"] < 100:
        issues.append(f"DMARC applies its policy to only {dm['pct']}% of failing mail.")
    if not spf["present"]:
        issues.append("No SPF record, so receivers have no list of servers allowed to send for this domain.")
    if not dm["present"]:
        issues.append("No DMARC record, so nothing tells receivers what to do with mail that fails authentication.")

    usable_spf = spf["present"] and spf["valid"] and spf["all"] != "+all"
    enforcing = dm["valid"] and dm["policy"] in ("quarantine", "reject")
    if enforcing and dm["pct"] == 100:
        verdict = "protected"
    elif (dm["present"] and dm["valid"]) or usable_spf:
        verdict = "partial"
    else:
        verdict = "exposed"

    return {"verdict": verdict, "spf": spf, "dmarc": dm, "issues": issues}


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
        result["error"] = "WHOIS lookup failed, the RDAP service was unreachable."
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
    those certificates reveal subdomains, a reliable, passive source that
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
    # Independent sources, so neither waits on the other.
    with ThreadPoolExecutor(max_workers=2) as pool:
        whois_future = pool.submit(whois_domain, domain)
        dns = dns_records(domain)
        whois = whois_future.result()

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
