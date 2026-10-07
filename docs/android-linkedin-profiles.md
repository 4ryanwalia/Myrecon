# Android Deep Search LinkedIn removal and retained adapters

LinkedIn has been removed from the mobile app's Deep Search source across email,
username and name searches. It no longer issues dedicated LinkedIn requests or
queries, or presents LinkedIn profile/status cards, career details, findings,
declared links or brief content. Saved-result presentation applies the same
filter so older payloads do not restore the removed feature.

This removal is source-only. No APK was rebuilt or installed for it; the user
will rebuild manually. Previously installed APKs retain their earlier behavior
until replaced. Google public profiles and Maps reviews remain available.

The standalone backend endpoint and shared adapters are retained. The following
notes describe those retained capabilities and historical validation, not an
active mobile Deep Search feature.

The backend can discover LinkedIn links declared on a public GitHub profile
associated with the exact email, or on the Gravatar profile addressed by that
email's hash. Historical commit associations remain labelled historical. Search
snippets and guessed email-prefix usernames never establish a LinkedIn account
connection.

For an independently established GitHub author profile, discovery reads LinkedIn
links from its website, public bio and public social accounts. The social-account
request is anonymous, uses the fixed GitHub API host, disables redirects and
environment proxies, and allows one request with 3-second connect and 5-second
read timeouts and a 100 KB response cap. It stays within the existing GitHub worker
budget. A social-source failure preserves links already found in the website or
bio and appears as a separate source status. Historical evidence stays historical.
Canonical LinkedIn URLs accept `linkedin.com`, `www.linkedin.com` and two-letter
country hosts such as `in.linkedin.com`; arbitrary subdomains are rejected.

`POST /api/email/linkedin-public` accepts `{"email":"fixture@example.com"}`.
It returns `query`, `status`, `profiles` and `sources`, with `Cache-Control: no-store`.
Discovery runs in bounded isolated workers: up to 25 seconds for GitHub and
12 seconds for Gravatar, in parallel. At most two established LinkedIn URLs are
read through the existing public adapter. No Google session, paid enrichment,
registration probes, Firebase writes, scan billing or result cache is used.

The adapter respects robots rules and access walls. It accepts only structured
data for the established canonical LinkedIn profile URL. Career fields include
the profile's headline, current work, work history, schools, degrees, fields of
study and dates when exposed. A missing job end date does not establish current
employment. Explicit false-current flags and concrete end dates prevent current
role promotion. Profile-listed current work is not real-time employment verification.

Before removal, the Android card showed source-listed current work, history and
education with expandable text and links to the profile and association evidence.
Duplicate dateless current roles were replaced by their richer dated record.
Missing or blocked details remained unavailable; an established profile link
stayed visible. The brief included at most three findings, with one per platform.

## Retained backend local setup

`tools/start-email-local.ps1` already enables `EMAIL_LINKEDIN_PUBLIC_ENABLED=true`.
The earlier installed debug build uses `http://localhost:5000`; it can still
call this endpoint until the user replaces it with a manual build. The current
mobile Deep Search source makes no LinkedIn lookup request. The local Google
review path still needs the running backend and `adb reverse tcp:5000 tcp:5000`.
Other build types retain an empty public-email endpoint. No production deployment
was performed.

## Validation on October 7, 2026

170 focused backend tests and 31 Android unit tests passed; `assemblePhoneDebug`
succeeded and the updated debug APK was installed on the connected phone.
Fresh phone Deep Search requests reached both local public-profile endpoints.
Fixtures exercise career fields, canonical identity matching, historical links,
access failures, worker isolation, current-role conflicts and duplicate roles.

The real local LinkedIn endpoint returned HTTP 200, `status: unknown`, and no
profiles for the user's original Gmail example: GitHub evidence existed, but
neither public source established a LinkedIn link. This does not prove the
person lacks LinkedIn. A live positive education/employment result has not been
verified. The Google endpoint still returned one contributor and two real
public reviews after the changes.

The subsequent GitHub bio/social-account discovery update passed 67 focused
backend endpoint/parser tests using fixtures. The complete relevant backend
regression set passed 206 tests across seven files. After restarting the local
backend with these changes, both `aryanwalia7888@gmail.com` and
`ashmilikhiya@gmail.com` returned HTTP 200, `status: unknown`, and no LinkedIn
profiles. The first email's GitHub author and public social-account checks
completed, but yielded no declared LinkedIn link. The second had no match in
the checked GitHub/Gravatar sources. These results do not establish absence
on LinkedIn or verify work/education.

Before the removal, Android source retained visible Google and LinkedIn status
sections, separated an unreachable lookup service from a completed check without
a link, and accepted the same strict country LinkedIn URLs as the backend. Mixed
Google source failures stayed unavailable in both the card and intelligence-brief
evidence. Six new Android
status/canonicalization test cases were added but not run: the user requested no
further builds. The earlier installed APK and 31-test result predate these source
changes. No Android rebuild, new APK installation or production deployment was
performed for this update.

LinkedIn can limit publicly visible fields even when a profile is public:
[LinkedIn public visibility limits](https://www.linkedin.com/help/linkedin/answer/a16659373).
Its approved [Profile API](https://learn.microsoft.com/en-us/linkedin/shared/integrations/people/profile-api/)
is not an unrestricted arbitrary-email search API. Reproducing a complete career
for every Gmail requires a separately authorized source of that information.

## Removal validation boundary on October 7, 2026

The removal was inspected statically in source. No Android or backend tests,
Gradle builds, APK installations or production deployments were run for this
removal. Earlier test counts and phone checks above apply to the prior feature
state and do not validate a rebuilt APK with the removal.
