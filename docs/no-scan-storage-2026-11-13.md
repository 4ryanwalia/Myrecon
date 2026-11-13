# Search storage and mobile access update — 13 November 2026

## Runtime contract

- Firebase keeps billing/subscription entitlements, referral claims/status and aggregate scan/allowance counts. Free account reads no longer create email/name profiles in Realtime Database. Firebase Authentication still owns Google sign-in identities.
- No scan results, searched identifiers, histories, ownership assertions or result-cache payloads are written to Firebase.
- Colab still receives active scan tasks through the authenticated API. The queue, leases and progress now live only in the single Render API process. Keep Gunicorn at **one worker** (multiple threads are supported).
- Completed jobs are removed after response delivery. An undelivered completed response buffer expires within 60 seconds. Active scans necessarily use temporary RAM and public-provider requests. Restarting Render loses active work; the former durable restart-resume guarantee no longer applies. Uncompleted paid allowances are refunded on the next account read using payload-free receipts; completion and count settle atomically.
- Normal lookup caches and the photo-response cache are disabled. Guest previews are sent directly; unlocking after sign-in requires a new search. No server-side guest-report reveal is retained.
- Per-account and anonymous aggregate counters contain no target, tool or result fields. Android sends an absolute, monotonic per-install count; retries cannot increase it. It is telemetry, not a trusted entitlement signal. A network failure can leave the cloud count behind until a later successful update.
- New Android search reports are no longer automatically archived or copied to the last-scan widget. Older local reports, explicit exports, browser saves and opt-in watch lists remain user-controlled.

## Existing data cleanup

`core/privacy_cleanup.py` runs in a background thread at API startup. It deletes the legacy `web/history`, `web/scans`, `web/scan_dispatch`, `web/scan_job_data`, `web/scan_dispatch_signal` and `web/match_choices` branches without downloading their payloads. It lists account IDs shallowly and strips name/email from accounts without purchase/subscription records. Billing, referrals, counters and entitlements are preserved. Completion is recorded under `web/metadata/no_scan_storage_v1`; transient failures retry three times and retry on the next process start if necessary.

`GET /api/health` reports `scan_storage.legacy_cleanup`. Confirm **complete** after deployment. This does not erase provider logs, Firebase Authentication identities, external-source records, user exports or backups managed outside the app database.

## Android behavior

- Version 1.15 / code 16.
- Existing Google Play Pro entitlement bypasses the Search/Enter full-screen ad for every lookup tool. Free standard lookups retain existing paced ads. Banner and native ad surfaces remain; Pro purchase text describes this accurately.
- Existing on-device Deep Search and Extended Scan remain available. The lock card now includes a direct referral share button.
- A Play-verified referral qualifies after the invited install completes one Standard scan. The inviter receives one Deep Search and one Extended Scan as a **one-time referral trial**. Repeated referral completions do not repeat the trial; pre-existing earned balances remain intact. Subscription access remains unlimited under the configured Google Play product.
- Prices come from the existing Google Play catalog and website providers; no example price is hardcoded or changed.
- Android sources are intentionally git-ignored in this repository. The local project and generated APK/AAB are separate from the website Git deployment. Google Play release upload and physical-device validation are separate checks.
