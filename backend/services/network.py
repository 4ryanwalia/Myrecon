"""Network intelligence service layer (domain / DNS / IP)."""

from modules import network


def scan_domain(domain: str) -> dict:
    result = network.domain_intel(domain)
    result["status"] = "ok"
    return result


def scan_dns(domain: str) -> dict:
    result = network.dns_records(domain)
    result["status"] = "ok"
    return result


def scan_whois(domain: str) -> dict:
    result = network.whois_domain(domain)
    result["status"] = "ok"
    return result


def scan_ip(ip: str) -> dict:
    result = network.ip_lookup(ip)
    result["status"] = "ok"
    return result
