# Email lookup reference review

Reviewed on October 1, 2026. Evidence: the user-supplied EmailOSINT result text and [EmailOSINT's public page](https://emailosint.org/). This is a comparison of one pasted report, not an independent verification of its matches or a coverage benchmark. The target email, credentials, personal biography and review text are intentionally omitted here and from test fixtures.

## What the supplied report contains

| Category | Reported findings | What the evidence actually means |
| --- | --- | --- |
| Registrations | 8: Zoom, Google, Wix, LinkedIn, GitHub, Duolingo, Spotify, HubSpot | The report claims registration, but the pasted text does not disclose the detection method for every service. |
| Detailed profiles | 6: Duolingo, GitHub, Google, LinkedIn, Wix, Zoom | Details range from an ID alone to extensive public profile fields. These six overlap with the eight registrations; they are not six additional accounts. |
| Identity summary | One reported name, three usernames, three profile pictures, four profile links | Links and usernames are useful pivots. A shared email association needs source evidence; a name match alone is insufficient. |
| Google | Profile ID, last-seen field, Maps activity, five reviews and nine answers | The report contains five review venue addresses and coordinates. These describe venues, not a residence or current location. The last-seen field's precise meaning is not explained. |
| LinkedIn | Biography, country, connections, skills, three positions and three education entries | Profile fields and date ranges should retain their source and any self-reported status. |
| Duolingo | Username, ID, creation date, language, timezone, subscription level, XP, streak, followers, following and linked-ID flags | A timezone setting is not location evidence. Google/Facebook ID flags are not additional discovered profiles. |
| Wix / Zoom | Service metadata and authentication method flags | These are service responses, not full public biographies. |
| Breaches | One entry with an unknown source label | An unnamed entry cannot establish which company breached the address. |
| Credential rows | 41 displayed rows, many repetitions tied to one additional domain | Row count is not unique credential count or unique account count. Raw leaked passwords must not become public test fixtures or report examples. |
| Timeline | Two events: a Google last-seen field and Duolingo creation | Positions, education and relative review dates are absent. The displayed first-seen value does not represent the earliest activity shown elsewhere in the report. |

## First implementation in MyRecon

- Add `evidence_report` to the existing email response without removing legacy fields. It derives its data from existing findings, makes no network requests, and adds no retention.
- Show separate counts for public profiles, registration signals, historical service associations and distinct named breaches. Counts overlap and must not be summed as unique accounts.
- Show names, usernames and self-reported profile locations with source attribution. Do not derive a person's name from the email local part or merge profiles into a claimed single identity.
- Enrich an exact-email GitHub match with allowlisted [public GitHub profile fields](https://docs.github.com/en/rest/users/users#get-a-user): name, biography, self-reported location/company, declared website, account creation and public stats. For commit-based matches, preserve the historical association if optional profile enrichment fails. Account creation does not date the email association; commit author dates are author-supplied. Profile update time is not presented as last activity.
- Present source events newest first with filters for profiles, public activity and breaches. Preserve year/month precision, reject malformed/future dates, and keep undated findings visible. Attribute conflicting breach dates to the specific source that supplied each date.
- Label the range as earliest/latest dated evidence instead of first/last use. A breach date describes the breach, not necessarily the time this exact address was captured.
- Keep the summary and timeline in copied text, JSON and CSV. Keep provider outages visible and avoid turning unavailable checks into clean results.
- Distinguish Gravatar owner-declared links from independently returned profiles, and historical GitHub commits from a current public-email association.

## Rich profile implementation

The second reference supplied by the user adds eight detailed profiles, eleven registration signals, eight Google review/rating items and three named breaches. These remain reference evidence, not locally verified discoveries. No target identifiers, passwords or personal review text are in fixtures.

The requested “What leaked about this address” bars and “Address analysis” section have been removed from the result UI. Source-backed breach categories remain in individual breach cards. The report now supports profile photos and links, usernames, expandable review venues, Google reviews with ratings/comments/owner replies/coordinates/source links, Google stats/apps, LinkedIn positions and education, service IDs/auth methods/boolean metadata, registration chips and an activity timeline. Copied text, JSON and CSV preserve the new fields. Dates with only a month retain month precision; relative review dates are displayed as supplied rather than converted to invented exact dates.

`backend/modules/email_enrichment.py` integrates the documented [OSINT Industries POST request](https://docs.osint.industries/reference/search-1) and [spec format](https://docs.osint.industries/reference/spec-format). It requires BOTH `EMAIL_ENRICHMENT_ENABLED=true` and `OSINT_INDUSTRIES_API_KEY` in the backend process environment. The existing linked-account toggle gates the request; it runs concurrently with the existing scan, with premium modules disabled and a bounded timeout. No key is exposed in frontend config. This backend does not automatically load `.env`; export variables through the local launcher or host configuration, then restart it. Provider requests use credits.

The parser consumes exact-query module results, keeps multiple profiles per module, distinguishes registration-only signals from detailed profiles, merges duplicate GitHub evidence without upgrading historical commit associations, and projects fields onto a bounded allowlist. Raw responses, secrets, passwords, contact containers and arbitrary nested metadata are excluded. Known platform-variable aliases are supported for rich collections. Live Google/LinkedIn collection field mappings still need verification against an authenticated production response; generic provider docs do not define every platform's nested data shape.

The official sandbox was reachable for a synthetic query, but returns generated platform data and was used only to inspect the spec envelope. Production has no sandbox fallback. Current local configuration has no OSINT Industries key; live rich results are therefore unconfigured, not complete. Both missing access and upstream failures are visible, and successful existing sources survive enrichment failure. The privacy provider table now discloses the optional integration.

## Remaining source gaps

Live Google reviews, LinkedIn details and the other service metadata still require an authenticated provider and known-positive/negative evaluation. Current upstream [GHunt email](https://github.com/mxrch/GHunt/blob/master/ghunt/modules/email.py) exports Maps statistics but sets reviews to null; its [Maps helper](https://github.com/mxrch/GHunt/blob/master/ghunt/helpers/gmaps.py) has review retrieval commented out. GHunt is therefore not assumed to deliver the requested review collection simply by being installed. Its profile-edit time is not last-seen activity.

The free [LeakCheck public API](https://docs.leakcheck.io/overview) provides breach sources and exposed categories, not actual leaked usernames/names/password values. A new optional [LeakCheck Pro adapter](https://docs.leakcheck.io/pro-api/lookup) now supplies exact-email historical usernames/names with dates and source flags. Enable both `EMAIL_BREACH_DETAILS_ENABLED=true` and `LEAKCHECK_APIKEY` in the backend environment. It bounds retrieval to 100 rows, deduplicates projected records, marks truncated/unattributable results partial, keeps credentials out of the API response, and preserves compilation/unverified flags. Password presence is shown; plaintext/hash value extraction is still incomplete relative to the expanded specification.

The latest expanded goal requests infrastructure again, superseding the earlier removal request. A new Email infrastructure section now lists every returned MX host with priority, reports disposable-list membership and plus-tag presence, and distinguishes MX routing from mailbox deliverability. A null MX means the domain rejects mail. Missing DNS results and ordinary MX records do not prove a mailbox exists. SMTP verification and plus-alias support remain unverified.

Provider additions require a supported integration, actual access, documented field meaning, evidence of exact-email association and outage handling. They must preserve the existing opt-in account-check choice and exclude message-triggering recovery actions. Broad platform counts and speed claims on the competitor's homepage remain its marketing claims, not verified benchmark evidence.

Remaining verification: connect a provider, validate the rich collection mappings using user-owned known-positive/negative accounts, and compare source coverage/errors. The new presentation and adapter are verified with synthetic tests; superiority in live coverage and speed remains unproven.
