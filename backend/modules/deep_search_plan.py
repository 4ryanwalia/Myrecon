"""Public name/handle query plans and exact-email routing, without guesses."""
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit

from core.validation import ValidationError, _strip, email, full_name

CATALOGUE = json.loads((Path(__file__).resolve().parents[1] / "data/deep_search_queries.json").read_text(encoding="utf-8"))
LABELS = {
    "Professional": "Professional & LinkedIn", "Social": "Social profiles",
    "InstagramFootprint": "Instagram footprint", "Discussions": "Comments & discussions",
    "News": "News & press", "Research": "Publications & research",
    "Records": "Companies & public records", "Documents": "Documents & pastes",
    "Mentions": "Other web mentions",
}


def parse_input(raw):
    raw = _strip(raw, "query")
    subject, _, context = raw.partition(",")
    explicit_handle = subject.strip().startswith("@")
    subject = subject.strip().removeprefix("@").strip()
    if not explicit_handle and "@" in subject:
        subject = email(subject)
        if context.strip():
            raise ValidationError("Enter the email address without extra context.")
        return {"subject": subject, "mode": "email", "context": None}
    mode = "name" if not explicit_handle and any(c.isspace() for c in subject) else "handle"
    if mode == "name":
        subject = " ".join(full_name(subject).split())
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}", subject):
        raise ValidationError("Enter an email, full name or a handle using letters, numbers, . _ and -.")
    context = context.strip()
    if context and (len(context) > 80 or not re.fullmatch(r"[\w .,'-]+", context)):
        raise ValidationError("Context must be a short city, employer or topic.")
    return {"subject": subject, "mode": mode, "context": context or None}


def build_plan(subject, mode, context=None):
    if mode == "email":
        return []
    values = {"h": subject, "q": '"' + subject + '"', "at": '"@' + subject + '"'}
    plan = []
    for item in CATALOGUE[mode]:
        query = re.sub(r"\$(h|q|at)\b", lambda m: values[m[1]], item["text"])
        if context:
            query += " " + context
        plan.append({"text": query, "section": item["section"], "label": LABELS[item["section"]],
                     "executed": False, "google": "https://www.google.com/search?" + urlencode({"q": query})})
    groups = {}
    for i, item in enumerate(plan):
        # The app offers third-party Instagram viewers as browser links only.
        if "picuki.com" not in item["text"] and "imginn.com" not in item["text"]:
            groups.setdefault(item["section"], []).append(i)
    order = [group[round_] for round_ in range(max(map(len, groups.values())))
             for group in groups.values() if round_ < len(group)]
    for i in order[:16 if mode == "name" else 18]:
        plan[i]["scheduled"] = True
    return plan


def normalise(text):
    return " ".join(re.sub(r"[^\w]", " ", text.casefold(), flags=re.UNICODE).split())


def matches_context(text, context):
    words = [w for w in normalise(context or "").split() if len(w) >= 2]
    hay = " " + normalise(text) + " "
    return bool(words) and all(" " + w + " " in hay for w in words)


def safe_url(raw):
    try:
        p = urlsplit(str(raw or ""))
        return str(raw) if p.scheme in ("https", "http") and p.hostname and not p.username else ""
    except ValueError:
        return ""


def accepts(query, hit):
    """Search results are mentions, accepted only against every query constraint."""
    url = safe_url(hit.get("url"))
    if not url:
        return False
    p = urlsplit(url)
    host = p.hostname.lower().removeprefix("www.")
    if any(host == h or host.endswith("." + h) for h in ("google.com", "bing.com", "duckduckgo.com")):
        return False
    site = re.search(r'\bsite:([^\s"]+)', query, re.I)
    if site:
        domain, _, path = site[1].lower().partition("/")
        if host != domain and not host.endswith("." + domain):
            return False
        # A path boundary avoids counting /nasa.fan as /nasa.
        path = "/" + path.rstrip("/")
        actual = unquote(p.path).lower()
        if path != "/" and actual != path and not actual.startswith(path + "/"):
            return False
    extension = re.search(r"\bfiletype:([a-z0-9]+)", query, re.I)
    if extension and not p.path.lower().endswith("." + extension[1].lower()):
        return False
    hay = " " + normalise(hit.get("title", "") + " " + hit.get("snippet", "") + " " + unquote(url)) + " "
    phrases = re.findall(r'"([^"\n]+)"', query)
    return all(" " + normalise(phrase) + " " in hay for phrase in phrases)


def is_profile(url, handle):
    parts = [unquote(p).removeprefix("@") for p in urlsplit(url).path.split("/") if p]
    if parts and parts[0].lower() in {"user", "u", "users", "in", "profile", "people", "channel", "c"}:
        parts = parts[1:]
    return bool(parts) and parts[0].casefold() == handle.casefold() and (
        len(parts) == 1 or (len(parts) == 2 and parts[1].lower() in
                           {"about", "posts", "videos", "featured", "overview", "reels", "tagged", "comments", "submitted", "repositories", "shorts", "streams"}))


def dedupe_key(url):
    return re.sub(r"^https?://(?:www\.|m\.|mobile\.)?", "", url.lower()).split("#")[0].rstrip("/")


def section_for(url, fallback):
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    for section, hosts in CATALOGUE.get("host_sections", {}).items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return section
    return fallback
