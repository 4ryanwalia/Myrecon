"""Rule-based evidence strength and freshness; never a probability of identity.

Collection time is not an activity date. Old account-creation dates do not make
current profile fields stale. Source count alone never boosts confidence.
"""
from datetime import date, datetime, timedelta, timezone
import calendar
import re

RULES = {
    "exact_public_email": (4, "Direct public association", "The source publishes this exact email on the profile; publication does not verify who controls the email."),
    "provider_email": (3, "Source-reported association", "The source returned this profile for the exact queried email; its mapping may be historical."),
    "email_hash": (3, "Email-hash association", "A public profile was returned for the queried email hash; current email ownership is not verified."),
    "public_link": (2, "Publicly linked profile", "An associated profile explicitly links this URL; the destination does not independently verify the email."),
    "historical_commit": (2, "Historical commit association", "An attributed public commit names this email; current account or email ownership is unknown."),
    "historical_public_link": (1, "Historical linked profile", "The public link comes from a historical email association; current common ownership is unknown."),
    "historical_breach": (1, "Historical exposure", "A breach source reports this past association; it does not establish a current account."),
    "registration_signal": (1, "Registration signal", "A service returned a registration signal without a verified profile or current ownership."),
    "review_venue": (2, "Source-reported review venue", "This is a place reviewed by the source-linked account, not evidence of residence or current whereabouts."),
}
METHOD_NOTE = ("Evidence strength uses fixed rules on a 0-4 scale, not a calibrated probability or identity verification. "
               "4: exact email published on a profile; 3: exact-query provider or email-hash association; "
               "2: public link, historical commit or review venue; 1: historical breach/link or registration signal; "
               "0: association basis unknown. Conflicting field values cap strength at 1. Source count does not increase the score.")


def confidence(basis, conflicting=False):
    score, label, reason = RULES.get(basis, (0, "Association unassessed", "The available data does not establish a supported association basis."))
    if conflicting:
        score, label, reason = min(score, 1), "Source values conflict", "Sources disagree about this field; inspect the retained alternatives."
    return {"score": score, "scale": 4, "label": label, "reason": reason, "method": "source-basis-v1"}


def _date_interval(value):
    """Reported date range; never invent a day for coarse source dates."""
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"\d{4}", value):
            return date(int(value), 1, 1), date(int(value), 12, 31)
        if re.fullmatch(r"\d{4}-\d{2}", value):
            year, month = map(int, value.split("-"))
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            day = date.fromisoformat(value)
            return day, day
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})", value):
            day = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).date()
            return day, day
    except (ValueError, OverflowError):
        pass
    return None


def freshness(basis, last_seen="", today=None):
    today = today or datetime.now(timezone.utc).date()
    result = {"status": "unknown", "label": "Recency unknown", "as_of": today.isoformat(),
              "reason": "No dated recency signal was supplied. Retrieval time does not verify recent activity."}
    if basis in ("historical_commit", "historical_breach", "historical_public_link"):
        result.update(status="historical", label="Historical association", reason="This evidence describes a past association; current ownership and activity are unverified.")
        return result
    if last_seen:
        interval = _date_interval(last_seen)
        if not interval:
            result.update(status="invalid_date", label="Recency date unusable", reason="The source recency date could not be interpreted; no activity date was inferred.")
        elif interval[0] > today:
            result.update(status="future_date", label="Source date is in the future", reason="The source date is later than this report; it cannot establish observed activity.")
        elif interval[1] < today - timedelta(days=365):
            result.update(status="potentially_outdated", label="Potentially outdated", reason="The latest possible day in the reported recency date is more than 365 days before this report; current activity is unknown.")
        else:
            result.update(status="source_reported", label="Source-reported recency", reason="A source supplies this recency date. It is not independently verified and does not date last use of the email.")
        result["reported_date"] = last_seen
    return result


def annotate_report(report, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    report["generated_at"] = now.isoformat().replace("+00:00", "Z")
    report["quality_version"] = 1
    report["confidence_note"] = METHOD_NOTE
    report["freshness_note"] = "Potentially outdated means the reported recency signal is over 365 days old. Profile creation, breach and review dates describe events, not present-day whereabouts or ownership."
    for profile in report.get("profiles", []):
        basis = profile.get("basis", "")
        profile["confidence"] = confidence(basis)
        profile["freshness"] = freshness(basis, profile.get("last_seen", ""), now.date())
        profile["field_assessments"] = {}
        for field in ("display_name", "username", "url", "avatar_url", "bio", "location", "fields", "stats", "lists", "positions", "education"):
            if profile.get(field):
                attribution = profile.get("field_sources", {}).get(field, {})
                field_basis = attribution.get("basis") if isinstance(attribution, dict) else None
                conflicts = profile.get("field_conflicts", {})
                profile["field_assessments"][field] = confidence(field_basis or basis, any(k == field or k.startswith(field + ".") for k in conflicts))
        for path, attribution in profile.get("field_sources", {}).items():
            if isinstance(attribution, dict):
                profile["field_assessments"][path] = confidence(attribution.get("basis", basis), bool(profile.get("field_conflicts", {}).get(path)))
        for path in profile.get("field_conflicts", {}):
            profile["field_assessments"][path] = confidence(basis, True)
        for review in profile.get("reviews", []):
            review["confidence"] = confidence("review_venue")
    for field, values in report.get("identity", {}).items():
        for row in values:
            row["confidence"] = confidence(row.get("basis", ""))
            row["freshness"] = freshness(row.get("basis", ""), today=now.date())
            matches = [p for p in report.get("profiles", []) if p.get(field) == row.get("value")
                       and p.get("platform") == row.get("source") and p.get("basis") == row.get("basis")]
            if matches:
                row["confidence"] = min((p["field_assessments"].get(field, p["confidence"]) for p in matches), key=lambda c: c["score"])
                row["freshness"] = matches[0]["freshness"]
    for row in report.get("locations", []):
        row["confidence"] = confidence(row.get("basis", ""))
        row["freshness"] = freshness(row.get("basis", ""), today=now.date())
    for row in report.get("registrations", []):
        row["confidence"] = confidence("registration_signal")
        row["freshness"] = freshness("registration_signal", today=now.date())
    for row in report.get("timeline", []) + report.get("undated_events", []):
        if row.get("kind") == "breach":
            row["confidence"] = confidence("historical_breach", row.get("date_conflict", False))
            row["freshness"] = freshness("historical_breach", today=now.date())
    return report
