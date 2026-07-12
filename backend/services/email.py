"""Email intelligence service layer — thin, JSON-safe wrapper."""

from modules.email_lookup import EmailLookup


def scan_email(email: str) -> dict:
    """Run the reliable email-intelligence pipeline and return JSON-safe data."""
    lookup = EmailLookup()
    result = lookup.scan(email)
    result["status"] = "ok"
    return result
