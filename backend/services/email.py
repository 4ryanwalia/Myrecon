"""Email intelligence service layer, thin, JSON-safe wrapper."""

from modules.email_lookup import EmailLookup


def scan_email(email: str, check_linked_accounts: bool = False) -> dict:
    """Run the reliable email-intelligence pipeline and return JSON-safe data."""
    lookup = EmailLookup()
    result = lookup.scan(email, check_linked_accounts=check_linked_accounts)
    result["status"] = "ok"
    return result
