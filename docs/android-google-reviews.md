# Android email lookup and Google reviews

The main Android variants now request exact-email Google public profiles from
`https://myrecon.onrender.com`, then show the contributor's public Google Maps
reviews. The hosted backend requires the production setup below. `phoneDebug`
can still use the local backend; its package is `com.Myrecon.osint.debug`.

The new `POST /api/email/public-profiles` route is separate from the full email
intelligence route. Its service calls the existing isolated GHunt identity
adapter and the bounded public Maps review reader. It does not perform breach,
registration or password-recovery checks, bill scan credits, write Firebase,
save reports or use the application result cache. Responses use
`Cache-Control: no-store`. Production deployment and Google operator login are
separate steps.

## Response contract

Request:

```json
{"email":"fixture@example.com"}
```

The response has `query.email`, `status`, `profiles` and `sources`. Each accepted
Google profile includes its contributor URL, public display name and photo,
`fields.ID`, optional `fields["Last profile edit"]`, public contribution counts,
`reviews`, `review_source` and `review_coverage`.

Each review may contain the venue name, address, text, rating, publication date,
source link, Maps link and owner reply when returned by the configured source.
Only these bounded public fields are projected. The response excludes session
material, contact containers, raw provider output and Google last-seen claims.
Profile edit dates describe profile edits, not online or login activity.

`review_coverage` keeps retrieval status, retrieved count, source-reported review
and rating totals, and whether the collection may be incomplete. The existing
reader requests one page, at most 100 records, for at most two established
contributors. Its unofficial Google response format may change. Missing,
private, blocked or unreadable collections remain inconclusive or unavailable;
they do not prove zero reviews. A Google profile survives review-fetch failure.

## Local setup

The isolated GHunt runtime is present in `output/ghunt-runtime-modern`. Operator
login was completed locally on October 7, 2026 and the exact-email lookup was
verified against the running local backend. A fresh installation still needs
the backend login below. Do not copy operator credentials into Android
resources, source control or chat.

1. Complete the upstream operator login locally:

   ```powershell
   & .\output\ghunt-runtime-modern\Scripts\ghunt.exe login
   ```

   The upstream Chrome Web Store link showed "This item is not available" on
   October 7, 2026. The official [Firefox listing](https://addons.mozilla.org/fr/firefox/addon/ghunt-companion/)
   was available. The companion must run in a browser that supports its
   extension, with the operator signed into Google there. Method 1 sends the
   session directly to GHunt's loopback listener on port 60067. Do not copy the
   Method 2 session value into chat. Installation permissions and Google sign-in
   are completed by the operator. On Windows, if the CLI exits with a banner
   encoding error, set `$env:PYTHONUTF8='1'` and
   `$env:PYTHONIOENCODING='utf-8'` before running it again.

2. Start the isolated local backend from the repository root:

   ```powershell
   .\tools\start-email-local.ps1
   ```

   The launcher enables `EMAIL_GHUNT_ENABLED` and
   `EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED` in that backend process and listens on
   loopback port 5000. Pass `-GhuntSessionFile` only when using a separately
   authenticated custom session location. Restart the backend after changing
   its configuration; this application does not automatically load `.env`.

3. For a USB-connected Android phone, forward the phone's loopback port:

   ```powershell
   adb reverse tcp:5000 tcp:5000
   ```

4. Build only the debug phone variant with the local public-profile API:

   ```powershell
   .\gradlew.bat assemblePhoneDebug -Pmyrecon.publicEmailApiBase=http://localhost:5000
   ```

   The public-profile endpoint setting is scoped to `phoneDebug`. It does not
   change the production API base or install/activate a Google session.

5. In the debug app, enter the email in Deep Search. A successful source match
   can show the Google contributor card and its retrieved public reviews.
   Disabled, unconfigured, expired-session, timeout and rate-limit states remain
   visible when the provider cannot complete the request.

The optional SerpApi review reader runs only if its existing backend flag and
key were configured separately. This change does not enable a paid provider or
invoke the unrelated paid email enrichment pipeline.

## Production setup (source prepared October 7, 2026)

The main Android variants use the production public-profile API. The Render
Blueprint now enables `EMAIL_GHUNT_ENABLED` and
`EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED`. Its build command is
`bash tools/build-render.sh`, which installs GHunt 2.3.4 in the separate
`backend/.venv/ghunt` runtime. The adapter discovers that runtime automatically;
an absolute `GHUNT_PYTHON_EXECUTABLE` still overrides it for other deployments.

In the Render service's secret environment settings, set `GHUNT_SESSION_B64`
to the **existing contents** of the operator-authenticated GHunt `creds.m` file.
GHunt already stores this file as base64: do not encode it again. The default
local login file is `%USERPROFILE%/.malfrats/ghunt/creds.m`; use the custom file
if your operator login used a different location. Transfer it directly into
the hosting secret field, never into source, Android resources, logs or chat.
Alternatively, mount that file as a hosting secret and set the absolute
`GHUNT_SESSION_FILE` path. A missing or expired session stays visibly
unconfigured or authentication-required.

For an existing Render service, apply the Blueprint's build command and both
feature flags in the dashboard, add the session secret, and deploy the changed
backend source. The secret is written only to a private temporary session file
for each lookup and removed afterward. Renew the dashboard secret after a new
operator login if Google invalidates the session.

Production setup was applied on October 7, 2026. Render's Myrecon service at
`https://myrecon.onrender.com` reports commit `9f89b678ea82a6deb67a4dae02851d3410aad489`
as live. The build command installs the isolated runtime, both Google flags
are enabled, and `GHUNT_SESSION_FILE` points to `/etc/secrets/ghunt-creds.m`.
The operator added the existing login file directly through Render. The worker
copies it to a private writable temporary file for credential refreshes.

Deployment completion was observed in the Render dashboard. No Google lookup
probe, Android build or test was run; the user will perform manual app testing.
The release and normal debug variants no longer depend on laptop port forwarding.

## Earlier verification boundary

Fixture tests cover the identity-to-review pipeline, isolated-runtime normalization, response projection,
candidate rejection, failure preservation, explicit no-match outcomes, input
validation and repeated uncached endpoint requests. They do not authenticate
GHunt or establish live review coverage. Device evidence is described below.

Local validation for this change: 119 focused backend tests and 20 Android unit
tests passed, and `assemblePhoneDebug` succeeded. Before login, a loopback request
returned HTTP 200 with `status: unconfigured` and no profiles. After login and
the compatibility fixes, the user-provided example email returned HTTP 200,
`status: ok`, one exact-email Google contributor and two public review records,
including ratings, venue details, text, publication dates and Maps/source links.
Both responses used `Cache-Control: no-store`. The debug APK was installed on the
connected Android phone with USB port forwarding to the local backend. Its
Google reviews section visibly rendered both real reviews, star ratings,
publication dates, venue details, review text and Maps/source buttons. The short
intelligence brief showed the Google review finding. A final debug rebuild was
installed, and the phone showed readable dates (`18 Aug 2024`, `11 Mar 2023`).
The long review's expand/collapse control was exercised successfully. This
verifies the local phone path; production deployment remains separate.

The identity worker requests GHunt's metadata-only exact lookup. This avoids its
current cover-photo parser failure and leaves review counts to the public Maps
reader, so a slow optional count request cannot discard a resolved identity.
Its normalization stays standard-library-only to work inside the isolated runtime.

LinkedIn was subsequently removed from mobile Deep Search source across email,
username and name searches, including dedicated requests, queries, cards and
saved-result presentation. The standalone backend endpoint and shared adapters
remain; see [LinkedIn removal and retained adapters](android-linkedin-profiles.md)
for its historical validation and current source boundary.

## Follow-up on October 7, 2026

Fresh local endpoint checks returned two public reviews for
`aryanwalia7888@gmail.com` and five for `ashmilikhiya@gmail.com`. After USB
forwarding was restored, the installed app displayed the second email's
five-review contributor result and review cards. The phone temporarily disappeared
from ADB and Windows' present USB-device inventory. After the user reconnected
it and forwarding was restored again, fresh searches for both emails reached
both backend endpoints with HTTP 200. The installed app visibly rendered five
reviews for Ashmil and two for Aryan, including ratings, dates, venue details,
text and Maps/source links. Screenshots are saved locally under
`output/google-reviews-phone/ashmil-fresh-connected.png` and
`output/google-reviews-phone/aryan-fresh-connected.png`.
The local backend remained healthy. This test
build depends on a working USB data connection, `adb reverse tcp:5000 tcp:5000`,
and the running laptop backend. Charging alone does not maintain that connection.

The latest relevant backend regression set passed 206 tests across the GHunt,
public-profile endpoint/projection, Maps reader, review integration and LinkedIn
endpoint/parser files. Before the LinkedIn removal, Android source kept both
public-profile sections visible when lookup failed and distinguished an unreachable service from an
explicit source no-match. Six additional Android tests were added but not run;
the user requested no further builds. These new status cards are not in the
previously installed APK. The backend discovery update is running locally;
there was no production deployment.

Email Deep Search no longer presents a YouTube channel/comment lookup step.
That step only examined declared URLs and added an empty no-match card without
requesting YouTube data. Real published YouTube links still appear under declared
links. Saved email reports omit the obsolete empty card and its evidence count;
username/name YouTube lookup paths remain available. This is an Android source
change only, with no new APK build or phone installation.

LinkedIn removal preserves the Google review request, contributor cards and
connection-status presentation. It also filters LinkedIn findings, published
links, identity/registry account entries, queries and brief content when showing
older saved Deep Search results. No new APK was built or installed for this
source-only removal; the user will rebuild manually. No tests were run for the
removal, so the earlier validation counts describe the previous implementation.
