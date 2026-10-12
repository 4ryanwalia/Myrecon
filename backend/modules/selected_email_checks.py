"""Reviewed email-only validation requests inspired by User Scanner (MIT).

No upstream code is executed. Only explicit responses become evidence; no
profile, ownership or absence is inferred. Provider bodies are discarded.
"""
SERVICES = [
    {"id": "huggingface", "name": "Hugging Face", "domain": "huggingface.co",
     "endpoint": "https://huggingface.co/api/check-user-email"},
    {"id": "hackerrank", "name": "HackerRank", "domain": "hackerrank.com",
     "endpoint": "https://www.hackerrank.com/auth/valid_email"},
]
for service in SERVICES:
    service.update(method="email validation", enabled=True, skip_reason="",
                   engine="MyRecon selected checks", source="User Scanner review")


def permitted(request, row):
    """Exact email-only POST allowlist in addition to the existing guard."""
    import json
    if request.method != "POST" or str(request.url) != row["endpoint"]:
        return False
    try:
        payload = json.loads(request.content)
    except (ValueError, TypeError):
        return False
    return (isinstance(payload, dict) and set(payload) == {"email"}
            and isinstance(payload.get("email"), str))


def verdict(service, response):
    if response.status_code in (403, 429):
        return {"rateLimit": True}
    try:
        data = response.json()
    except ValueError:
        return None
    if service == "huggingface" and response.status_code == 200:
        # Accept only a JSON string or a message object; HTML stays unknown.
        message = data if isinstance(data, str) else data.get("message") if isinstance(data, dict) else None
        if isinstance(message, str):
            if "already exists" in message.lower():
                return {"exists": True}
            if message.strip() == "This email address is available.":
                return {"exists": False}
    elif service == "hackerrank" and response.status_code == 200 and isinstance(data, dict):
        errors = data.get("errors")
        messages = [errors] if isinstance(errors, str) else errors if isinstance(errors, list) else []
        taken = data.get("internal_status_code") == "already_registered" or any(
            isinstance(message, str) and "already registered" in message.lower() for message in messages)
        if taken and data.get("status") is not True:
            return {"exists": True}
        if data.get("status") is True and not errors and not data.get("internal_status_code"):
            return {"exists": False}
    return None


async def check(email, client, row):
    payload = {"email": email}
    response = await client.post(row["endpoint"], json=payload,
                                headers={"Accept": "application/json"})
    return verdict(row["id"], response)
