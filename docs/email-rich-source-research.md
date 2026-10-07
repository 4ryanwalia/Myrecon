# Rich email profile sources

Research checked 2026-10-01. This records public documentation and public client code, not a successful credentialed production lookup.

## What EmailOSINT reveals publicly

[EmailOSINT's homepage](https://emailosint.org/) describes public profile validators, breach feeds and an AI synthesis layer. Its published interface separates identity results from breaches. Its public [results renderer](https://emailosint.org/assets/results-view-R4mkLOmK.js) reads `data.fields` entries containing keys, types and values. It has dedicated renderers for `linkedin_positions`, `linkedin_education`, `google_reviews`, `google_ratings`, `google_answers`, `google_q_and_a`, `google_photos` and `google_stats`.

The renderer expects job company/name/logo, split year/month dates, education degrees and subjects, and review venues nested under `location.position`. That demonstrates the presentation shape, not how the server obtained it. No inspected public source establishes that EmailOSINT uses OSINT Industries, PDL, SerpApi or any particular upstream identity supplier. Similar field names are not proof of shared infrastructure. Its API and JavaScript do not disclose a reproducible no-key email-to-LinkedIn lookup mechanism.

## Implemented retrieval paths

### OSINT Industries

The existing adapter uses the documented [POST search endpoint](https://docs.osint.industries/reference/search-1) and [spec format](https://docs.osint.industries/reference/spec-format). It consumes the provider's own wrapper, never the competitor's payload. It now preserves first/last names, split career dates, nested public review venue fields and known Google statistics where those aliases are actually returned. Platform-specific aliases are defensive compatibility handling; their presence in live provider output has not been verified. `reliable_source: false` results are excluded from asserted profiles. Empty or unrelated responses are partial, not a clean negative result.

Prerequisites: `EMAIL_ENRICHMENT_ENABLED=true` and `OSINT_INDUSTRIES_API_KEY`. The provider timeout is 25 seconds; slower modules can be omitted according to its documentation. Commercial redistribution permission must match the deployment's agreement; the provider's published [API terms](https://www.osint.industries/api-terms-of-use) should be checked for the intended product use. No sandbox data is used as evidence.

The POST response is streamed through the same bounded JSON reader used by the other adapters and closed on success or failure. Every reader caps decoded response bytes at 2 MB and body processing at 20 seconds, checking a monotonic deadline between reads. PDL and SerpApi additionally include header waiting in a 20-second request deadline; OSINT Industries uses 45 seconds to accommodate its minimum 25-second processing window. Socket timeouts bound individual blocked reads. These elapsed checks are not a hard watchdog: an in-progress socket read can finish after the deadline before the next check rejects it.

### LinkedIn via People Data Labs

[PDL Person Enrichment](https://docs.peopledatalabs.com/docs/person-enrichment-api) provides an actual documented email enrichment API, independent of the OSINT Industries key. `enrich_linkedin_email(email)` sends only the queried email with a restricted output projection. It uses [`min_likelihood=6`, `include_if_matched=true`, and `required=linkedin_url`](https://docs.peopledatalabs.com/docs/input-parameters-person-enrichment-api). It accepts a profile only when the provider declares an email match and the exact queried email occurs in the returned email fields. A name match, guessed handle, high score alone or profile URL alone is insufficient.

Projection follows the [documented person schema](https://docs.peopledatalabs.com/docs/fields): name, summary, general locality/region/country, LinkedIn connections, nested company/title work history, and school/degree/subject education. It does not output extra emails, phone numbers, street addresses or raw provider objects. Missing fields stay absent. The provider is an aggregated dataset; the evidence label explicitly does not claim current LinkedIn account verification. Photos are not promised by this adapter's verified schema and are not manufactured.

Prerequisites: `EMAIL_LINKEDIN_ENRICHMENT_ENABLED=true` and `PDL_API_KEY`, with the provider plan and rights needed for the selected fields. One fixed-host HTTPS request, redirects disabled, 3-second connect and 12-second read timeouts, 2 MB response limit. Status 404 means no provider dataset match, not that the LinkedIn account does not exist.

[LinkedIn's official Profile API](https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-api) requires approved access and authenticated authorization, subject to member privacy settings. It is not an unrestricted reverse-email endpoint. No login, cookies or private-profile scraping has been introduced.

### Google contributor reviews via SerpApi

[SerpApi's contributor reviews API](https://serpapi.com/google-maps-contributor-reviews-api) requires a numeric Google Maps contributor ID. It is not an email identity resolver. `enrich_google_reviews(result)` only requests details for a Google profile that already has `basis=provider_email`, `profile_status=ok`, and a source-reported contributor ID or allowlisted Google Maps contributor URL. It does not guess an ID from an email name.

Prerequisites: `EMAIL_GOOGLE_REVIEWS_ENABLED=true` and `SERPAPI_API_KEY`, plus an established Google profile. This integration requests at most 100 records. No undocumented cursor is followed. A response must echo the contributor ID. Projections include venue coordinates, text, rating, relative dates, links, `response.snippet`/`response.date` owner replies, and `contributor.contributions` review/rating/answer/photo counts. Reaching the cap or receiving fewer reviews than the reported count is partial. Review venues do not establish residence. At most one contributor request runs per enrichment call.

## Integration and validation

`modules.email_enrichment.enrich_email(email)` retains its existing return contract (`status`, `profiles`, `registrations`, `sources`) and automatically invokes the optional PDL path even if OSINT Industries is unconfigured. Google reviews supplement an OSINT Industries Google profile only when needed. All source diagnostics use fixed messages, with no secret-bearing response bodies.

An attempted failure alongside any completed source or positive profile makes the aggregate partial and preserves all positive findings. If every attempted source fails, the aggregate reports a specific failure (authentication, credits, rate limit) or unavailable, never ok or unconfigured. Positive profiles with other optional providers unconfigured are explicitly partial coverage. An unconfigured optional source is not treated as an attempted provider outage.

Synthetic offline tests cover exact-email rejection, identity mismatches, nested mappings, missing credentials, HTTP errors, private-field exclusion, response limits, redirects, and no guessed contributor requests. A credentialed live lookup and provider-plan entitlement check remain required before claiming live LinkedIn or Google review coverage. Existing public GitHub and Gravatar evidence remains useful when these optional sources are unconfigured.
