# Email intelligence implementation audit

Updated October 1, 2026 against the expanded goal and the latest request to fix duplicates, photos and rich profiles. The latest request removes the infrastructure section from the dashboard; backend analysis remains available in structured data. The full goal is **not achieved**. Synthetic fixture checks prove rendering/adapter behavior, not live provider coverage.

| Requirement | Current authoritative implementation | Remaining proof/work |
| --- | --- | --- |
| Format/syntax | `core/validation.py` validates supported ASCII email syntax before network calls | International/quoted-address support is not implemented |
| Provider, disposable, plus-addressing | `EmailLookup.analyze` identifies common providers, checks local disposable list and tag presence | Provider alias support detection and broader maintained disposable source |
| Deliverability, SMTP | MX routing is distinguished from mailbox deliverability; null MX handled | SMTP test, catch-all/greylist handling, outbound-port verification |
| All MX hosts/priorities | All returned MX records parsed and sorted in JSON; dashboard section removed at latest user request | Resolver failure vs authoritative empty responses need separate outcomes |
| Multiple breach sources | Free LeakCheck + XposedOrNot; optional LeakCheck Pro | HIBP and Dehashed integrations + authenticated live evaluation |
| Historical usernames/names | Optional exact-email LeakCheck Pro records projected into source-attributed summary and breach cards | API key/live validation; plaintext/hash value extraction still absent |
| GitHub | Official public profile/commit API, photo, username, ID, repo stats, bio/location | Configured token and known-positive/negative evaluation; no completeness guarantee |
| LinkedIn | OSINT Industries profile projection plus independent People Data Labs exact-email enrichment; nested jobs/education/cards and source diagnostics | API access and real returned field/plan validation; PDL does not promise a photo or live account verification |
| Google | OSINT Industries identity projection plus SerpApi contributor-review retrieval for an established ID; nested venues/date/text/GPS links | Authenticated identity/review sources; contributor retrieval capped at 100 and marked partial at limit, no documented pagination implemented |
| Registrations | Existing bounded opt-in Holehe catalogue + optional provider signals; IDs/auth/verified flags displayed when returned | Verify each requested platform with live control accounts; unavailable modules stay unknown |
| Locations | Source-reported profile fields and review venues, expandable list, coordinates/maps links in review cards | Normalize geography/geocoding; listing coordinates in location summary itself |
| Timeline | Compatible same-breach dates merged at best reported precision with original dates retained; conflicting dates stay distinct; repeated profile events consolidated | Verify provider date meanings and coverage; not all APIs supply each event |
| Gallery and unavailable photos | Shared URLs appear once in gallery; public CDN retry route with pinned public DNS/TLS, bounded raster validation and five-minute cache; final failures show initials | Private/expired photos remain unavailable; profile-photo EXIF extraction is absent |
| Rate limiting/scraping | Existing per-source timeouts/statuses; optional adapters expose failures; no recovery-message calls | Scraping robots handling, per-provider throttling/retry, any authorized proxy strategy |
| JSON/CSV | Existing downloads include new structured evidence | Confirm production source fields; credential export policy once those fields exist |
| PDF | Print-to-PDF path expands folded findings; generated nine-page fixture verified by text extraction and inspection of all nine rendered pages | Live rich report still requires provider access |
| Caching | Public photo bytes have bounded five-minute memory/browser caching; email reports remain uncached | Full result caching and associated privacy/tests still absent |
| Confidence/outdated flags | Source/basis attribution and historical association labels exist | Confidence scores/methodology, timestamps and staleness flags absent |
| Dashboard framework | Existing vanilla-JS dashboard extended in place | React/Vue was preferred; no framework migration performed |

## Provider limits verified from primary sources

- [Google People searchContacts](https://developers.google.com/people/api/rest/v1/people/searchContacts) searches the authenticated user's contacts. It is not an arbitrary email-to-public-profile directory and should not be presented as such.
- [Google Place Details](https://developers.google.com/maps/documentation/places/web-service/place-details) retrieves a place by ID; it does not resolve an email to all reviews by that account.
- [OSINT Industries spec format](https://docs.osint.industries/reference/spec-format) supplies standardized profile fields and platform variables. The generic schema does not prove Google/LinkedIn nested field mappings or completeness.
- Current [GHunt Maps helper](https://github.com/mxrch/GHunt/blob/master/ghunt/helpers/gmaps.py) has review retrieval commented out. Installing GHunt alone does not establish review support.

## Configuration and outstanding acceptance

Local environment checks found no OSINT Industries, People Data Labs or SerpApi keys, or authenticated GHunt configuration. New provider adapters do not call a sandbox or invent records if unconfigured. No LeakCheck Pro key is configured in the local process either. Access must be configured on the backend, not pasted into frontend config or committed. Prerequisites and verified provider contracts are in `docs/email-rich-source-research.md` and `backend/.env.example`.

Keep the goal active. Next implementation passes must address missing modules and quality requirements, then validate live known-positive/negative accounts. Full completion requires requirement-by-requirement evidence; green synthetic tests are insufficient.

Latest checkpoint: 205 targeted backend tests, 25 frontend tests, browser journey checks at desktop/375/390/768px, JSON download parsing, direct-photo failure/proxy success and terminal-photo fallback. A live local photo route request for a generic Gravatar identicon returned PNG bytes with the expected CORS/CORP headers; no personal target lookup was performed. Earlier nine-page PDF fixture was inspected before this UI cleanup; the latest browser pass skipped PDF regeneration. This is implementation evidence, not proof of the pending live source requirements.

Open-source follow-up: optional GHunt 2.3.4 isolated public-only worker, robots-aware LinkedIn JSON-LD reader for source-established URLs, explicit GitHub public-link correlation preserving historical basis, and manual username-scanner handoff added. 254 targeted backend tests, 25 frontend tests and the updated browser journey passed. Isolated GHunt import/authentication-failure smoke passed; operator login is pending. Individual Google reviews remain unsupported by current upstream GHunt. See `docs/email-open-source-stack.md` for requested-project assessment and setup. Full commercial-source replacement remains incomplete.
