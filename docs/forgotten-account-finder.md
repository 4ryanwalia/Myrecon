# Forgotten Account Finder and Before You Meet

Local implementation, not deployed or published. No pricing, payment, production configuration, OCR, screenshot input, new AI processing, or analytics payload changes.

## Reused flows

All three entry points select the existing username lookup on the website and Android. Existing scan admission, authentication, quotas, Android ad pacing, cancellation, result cards, source checking, and history remain in use. One handle is scanned at a time; no batch fan-out was introduced.

Existing strict profile parsing and Android text shares support Instagram, TikTok, and GitHub profile URLs. Host allowlists and full route matching reject lookalikes, posts, reels, repositories, reserved routes, and ambiguous shares. Tracking is removed locally. Unsupported links need a username or a supported full profile URL; no arbitrary URL resolution was added.

## Ownership and cleanup

Website choices use the existing private account endpoint; guest choices remain in this browser. Android choices are local DataStore records keyed by canonical profile URL (which includes platform identity), with a user-recorded timestamp. Current choices apply when revisiting reports and later scans. These are user assertions, separate from immutable provider evidence; they do not establish identity. Android and website choices do not sync with each other.

Only distinct found profiles explicitly marked Mine enter confirmed totals and promotional recaps. Not mine, Unsure, missing choices, and inconclusive checks do not. No rediscovered claim is made. Handle exposure scores were removed from these results. Cleanup uses the existing guidance and controls after Mine: Keep, Review, Removal requested. Existing Android Deleted records remain labeled as user-recorded completion; website completion is also explicitly self-recorded. Neither is verified deletion. Changing ownership hides cleanup and excludes the record from confirmed cleanup totals. Existing privacy/deletion controls remain available; Android history also exposes clearing ownership choices.

## Reports and return visits

Source URLs and evidence remain in shared result cards. Reports display last-check time; older website reports without a recorded check time say so. Saved website reports now preserve check time, source evidence, platform-check coverage, and a separately labeled original profile URL. Android saves the original URL separately from results. History restores the existing Android results UI so choices can be revised without rescanning.

Android comparison separates newly discovered profiles, changed supplied public profile details, and coverage changes. Missing or failed checks do not assert disappearance. Missing metadata is not treated as a confirmed detail change. Existing weekly Android monitoring remains opt-in, rotates a bounded batch of three handles, uses unique WorkManager jobs, preserves observed profiles across failed checks, establishes source baselines silently, and reports its last successful check. Monitoring alerts identify new public profile findings; content-change monitoring is not added. Website background monitoring is not added.

## Sharing

Android extends the existing image-preview/share sheet. Website adds a count-only recap preview alongside existing report sharing. Recaps accept only the confirmed count and canonical MyRecon link; usernames, names, photos, emails, platform lists, profile URLs, scores, and other identifiers are absent. Sharing requires a separate explicit action after preview. Full report sharing is separately labeled and retains its existing purpose.

## Files and handoff

The checkout contains substantial pre-existing uncommitted work. Android source is ignored by the repository's current Git rules. Modified local Android paths under app/src/main/java/com/aryan/myrecon:

- data/Discovery.kt (new), ReconStore.kt, ReportComparison.kt
- ui/screens/LookupScreen.kt, LookupViewModel.kt, LookupReports.kt, ResultViews.kt, HistoryScreen.kt
- ui/components/Cleanup.kt, ShareCard.kt
- widget/ExposureWidget.kt, work/HandleWatchWorker.kt
- New focused tests: app/src/test/java/com/aryan/myrecon/DiscoveryTest.kt

Website changes extend app.js and match-choices.js, add discovery.js, and load it from index.html and app.html. Backend extends existing match choices and history serialization, with scan timestamps added at actual completion. Do not rely on git diff alone to transfer the ignored Android files.

## Validation boundaries

Mocked browser and backend checks do not establish real provider availability or production database behavior. Android compilation and JVM tests do not establish real-device share-sheet rendering, text-share lifecycle behavior, notification delivery, or background scheduling. Those remain device checks. Public sources may be unavailable; this does not prove deletion or safety. No commercial-policy change is required.

## Local check results

- 126 backend tests passed across profile parsing, accounts/entitlements/history/choices, search resilience, and username streaming.
- 38 frontend tests passed across discovery counts/redaction, parsing, access limits, and source failures.
- Browser journeys passed for automatic paste, canonical handles, ambiguity, repeated input, cancellation, typed submission, guest access, streaming, mobile overflow, ownership/account isolation, failed-save rollback, cleanup persistence, and redacted recap preview/cancel/count updates.
- Focused Android JVM suites: DiscoveryTest, MonitoringPolicyTest, ProfileInputTest, SavedReportsTest, ScoreCardTest, SharedInputTest (38 tests, zero failures).
- Debug assemble passed. The broad Android unit-test attempt was stopped when existing BreachFallbackTest waited on network providers; it is not reported as a full-suite pass.
- Logs are in build_temp/discovery-*.log. No physical device or production verification was performed.
