"""Fixed, reviewed User Scanner allowlist. No path discovery or dynamic imports."""
from dataclasses import dataclass
from types import MappingProxyType

SOURCE = "https://github.com/kaifcodec/user-scanner"


@dataclass(frozen=True)
class ModuleSpec:
    id: str
    name: str
    scan_type: str
    category: str
    reference_module: str
    hosts: tuple[str, ...]
    metadata: tuple[str, ...]
    enabled: bool = False
    dependency: str = "requests"
    source: str = SOURCE
    license: str = "MIT"


REGISTRY = MappingProxyType({
    "username.github": ModuleSpec(
        "username.github", "GitHub", "username", "dev",
        "user_scanner/user_scan/dev/github.py", ("api.github.com",),
        ("name", "bio", "company", "location", "followers", "following", "public_repos", "created_at")),
    "email.gravatar": ModuleSpec(
        "email.gravatar", "Gravatar", "email", "social",
        "user_scanner/email_scan/social/gravatar.py", ("en.gravatar.com",),
        ("display_name", "username", "bio", "location")),
})
STATES = ("found", "not_found", "no_match", "unavailable", "skipped", "rate_limited", "timeout")
MAX_MODULES = 2
MAX_OUTPUT = 16_384
SCAN_SECONDS = 20
MODULE_SECONDS = 9


def outcome(spec, status, reason, *, metadata=None, url="", status_code=0):
    """Only allow public scalar fields for confirmed findings; no raw bodies."""
    clean = {}
    if status == "found" and isinstance(metadata, dict):
        for key in spec.metadata:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                clean[key] = value.strip()[:512]
            elif type(value) is int and 0 <= value <= 1_000_000_000:
                clean[key] = value
    return {"id": spec.id, "platform": spec.name, "service": spec.name,
            "scan_type": spec.scan_type, "category": spec.category,
            "source": spec.source, "reference_module": spec.reference_module,
            "license": spec.license, "status": status, "reason": reason,
            "url": url, "status_code": status_code, "metadata": clean}
