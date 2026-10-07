# Email platforms and public reviews

Implemented and checked on October 1, 2026, against the logged-in EmailOSINT
dashboard and an existing saved report. No target emails, personal review text,
credentials or raw provider responses were added to fixtures or this document.

## What changed

- `platform_summary` reports distinct platforms, with separate source-associated
  profiles, registration signals, historical associations and owner-declared links.
  Repeated profiles, overlapping registration checks and service aliases count
  once. Categories overlap and are not summed as an account total. Historical
  evidence alone does not establish a current account. OpenPGP is auxiliary
  evidence, rather than a social platform.
- Source failures and inconclusive registration checks remain visible. A positive
  registration signal is not ownership verification. The ordinary username
  platform sweep and its catalogue are unchanged.
- The email overview shows linked platforms before the detailed report. Google
  cards distinguish review text, rating-only contributions, source-reported
  review/rating counts, retrieved records and unavailable collections.
- Copied summaries and JSON/CSV exports retain the platform and review coverage
  separately from breach coverage. Duplicate Google identities share a request;
  conflicting source counts remain attributed instead of being overwritten.

## Free public review source

`backend/modules/email_maps_public.py` makes a bounded anonymous request to the
public Google Maps contributor endpoint. The caller must already have a Google
contributor ID established by an exact-email source. It does not resolve emails,
guess contributor IDs, forward Google cookies or read private account data.

The request is limited to one page, 100 records, two distinct contributors per
email report, 2 MB per response and a 20-second response budget. Socket timeouts
also bound individual waits. Missing or changed response layouts remain unknown.
An empty collection is not a zero claim unless readable public context explicitly
reports both zero reviews and zero ratings. Public reviews include safe venue,
rating, text, date and contributor/place links where returned. Venue coordinates
describe reviewed places, not a home or current location.

The experimental wire format was checked against
[Account-Lens's public protocol reference](https://github.com/FR46M3N7-P4R71CL3/Account-Lens/blob/main/extension/background.js).
The parser and transport are independently implemented. The source uses an
unofficial Google response format and may stop working. The existing documented
[SerpApi contributor source](https://serpapi.com/google-maps-contributor-reviews-api)
remains an optional provider; it runs first when configured, and its failures
remain visible even if the free source succeeds. Upstream GHunt returns Google
identity and contribution counts; it does not currently provide review bodies.

Enable the anonymous source with:

```text
EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED=true
```

The existing linked-account toggle gates all profile enrichment. The local
`tools/start-email-local.ps1` launcher now enables the free review source along
with the existing Google identity adapter. Environment changes require restarting
the backend. Optional provider keys remain backend-only.

## Verification and remaining boundary

The anonymous source returned two readable public review records in a live
request for a contributor link observed in the saved reference report. Both
records had review text and source links, and the response's own counters reported
two reviews and zero ratings. This verifies that request and response shape for
one public contributor on this date, not general coverage or parity with the
competitor. No public review text or raw response was saved.

The local GHunt runtime exists, but its operator session file is absent. End-to-end
email-to-Google identity lookup still requires the operator to complete upstream
GHunt login, or an already configured exact-email provider. Public review fetch
success does not verify that identity step. These changes are local and have not
been deployed.

Offline checks cover alias counts, historical/current overlap, unknown checks,
identity boundaries, malformed records, response/time bounds, public review IDs,
source links, fallback behavior, retained profile evidence, export status and
markup/URL escaping. The browser journey additionally checks dark/light themes,
375/390/768-pixel layouts, photo fallback, opt-in controls and report export.

Final validation: 398 targeted backend tests and 52 frontend tests passed. The
real browser journey passed, and desktop/mobile screenshots were visually checked.
