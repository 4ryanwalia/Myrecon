# Open-source email intelligence sources

This is a partial replacement stack, not a clone of a commercial identity database. No provider is assumed to identify every email address. The dashboard keeps source coverage, unknown results and historical associations visible.

## Implemented

| Capability | Source | Actual behavior |
| --- | --- | --- |
| Email registration signals | Holehe, pinned reviewed revision | Existing bounded worker; excludes requests that send recovery messages or submit credentials. A registration signal is not a profile URL or proof of ownership. |
| Email-linked GitHub | GitHub public API | Existing exact published email or exact historical commit-email association. Photos, bio, location, creation date and public repository count when returned. |
| Google identity | GHunt 2.3.4 isolated library worker | Public PROFILE ID, available photo, apps, enterprise field, profile edit date and Maps counts. Operator login required. No Calendar or private data collection. |
| LinkedIn public details | Public JSON-LD reader | Reads a previously source-linked `/in/` URL, including an explicit link on an email-associated GitHub profile. Checks robots.txt and page identity. No guessed slugs, authenticated scraping or private API. |
| Handle discovery across platforms | Existing MyRecon username scanner | Email summary has a manual Search this username action using the exact reported handle. Results are handle matches; they do not independently prove common ownership. |
| Breach exposure | Existing LeakCheck/XposedOrNot adapters | Source-attributed historical exposure metadata. Raw credential values are not exported. |

## GHunt setup

GHunt needs Python 3.10 or newer. This machine's backend Python is 3.9, so a separate Python 3.12 environment was installed at `output/ghunt-runtime-modern` with `ghunt==2.3.4`. It is ignored by Git and is not a production dependency.

1. Use the isolated environment's `Scripts/ghunt.exe login` locally and complete the upstream operator login. Authentication material must stay private on the backend. Do not paste cookies into chat or frontend configuration.
2. Set process environment variables:

```text
EMAIL_GHUNT_ENABLED=true
GHUNT_PYTHON_EXECUTABLE=<absolute path to isolated Scripts/python.exe>
GHUNT_SESSION_FILE=<absolute path to authenticated GHunt creds file>
EMAIL_LINKEDIN_PUBLIC_ENABLED=true
```

3. Restart the backend and enable linked-account checks in the email dashboard. `tools/start-email-local.ps1` enables the free sources and uses the upstream default session path `%USERPROFILE%/.malfrats/ghunt/creds.m`; pass `-GhuntSessionFile` for another path. Stop any existing local backend before starting it. This app reads process environment; merely editing `.env` does not load these settings.

The adapter reports unconfigured, authentication required, timeout or unavailable without erasing other results. It launches a bounded worker without placing the email in command arguments. Session data is never forwarded to the browser.

**Google review support:** current GHunt code has individual review parsing commented out. Its adapter returns available contribution counts and a public Maps contributor link. A separate bounded anonymous Maps reader now retrieves public reviews for an already source-established contributor ID; enable `EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED=true` (the local launcher does this). One live contributor request returned readable review records. This unofficial response format can change; unknown/private/blocked responses do not establish zero reviews. The optional SerpApi adapter remains available and requires its own key. See [the platform/review upgrade](email-platform-review-upgrade.md) for the verification boundary and coverage contract.

**LinkedIn limitation:** a public reader cannot resolve every email to LinkedIn. A profile URL must first be established by a source. Robots exclusion, login walls and absent structured data remain unavailable. Fields missing from public JSON-LD remain absent, including connection counts and career dates.

## Other requested projects

| Project | Assessment |
| --- | --- |
| Sherlock, nexfil | Username enumeration, already covered by the existing scanner. Installing several parallel engines would repeat requests and does not establish email ownership. |
| social-analyzer | Separate profile analysis framework; not an arbitrary email-to-identity database. Not integrated in this pass. |
| Infoga, theHarvester | Domain/search-engine footprint discovery, not exact email-to-LinkedIn enrichment. Not integrated in this email path. |
| Recon-ng, SpiderFoot | Frameworks with their own module configurations and provider requirements. Not a drop-in free data supplier; not integrated. |
| linkedin-scraper | Current upstream uses browser sessions. Not installed; this integration reads allowed public structured data without LinkedIn login. |
| h8mail | Aggregates third-party services or searches operator-supplied local breach files. Installation does not provide LinkedIn breach dumps. Not installed and no breach dumps downloaded. |
| email2linkedin, linkedin-enrichment, email-miner, prospector | Supplied names lack verified maintained repository/endpoint contracts. Not added as speculative integrations. |
| linkedin2username | Generates possible employee usernames from company information; generated names are candidates, not discovered email-linked accounts. Not used for automatic identity claims. |
| SERP scraper projects / Scrapy | Scraping infrastructure does not itself supply Google identity or contributor review data. No CAPTCHA or access-control bypass added. |

Free-tier quotas in the supplied list were not used as implementation assumptions. Each external service requires separately verified current access and coverage.

## Primary references

- [Holehe schema and modules](https://github.com/megadose/holehe)
- [GHunt install and operator login](https://github.com/mxrch/GHunt)
- [GHunt email module](https://github.com/mxrch/GHunt/blob/master/ghunt/modules/email.py)
- [GHunt Maps helper](https://github.com/mxrch/GHunt/blob/master/ghunt/helpers/gmaps.py)
- [h8mail sources and local search](https://github.com/khast3x/h8mail)
- [Sherlock username search](https://github.com/sherlock-project/sherlock)
- [LinkedIn scraper](https://github.com/joeyism/linkedin_scraper)
- [linkedin2username](https://github.com/initstring/linkedin2username)

## Acceptance limits

Synthetic parser, failure, identity-boundary and browser tests cover implementation. No authenticated GHunt target lookup or live LinkedIn profile enrichment has been validated locally. A complete replacement of the requested services has not been achieved.

Latest validation: 254 targeted backend tests, 25 frontend unit tests, browser checks for manual username follow-up, photo fallback, timeline filters, exports, dark/light and 375/390/768px layouts. The actual isolated GHunt worker returned authentication_required for an empty synthetic session without a target network lookup. Local frontend and backend health returned HTTP 200.
