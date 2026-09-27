# Usability fixes — 18 September 2026

> Archived point-in-time report. The Android source discussed here is outside
> this repository; results and build evidence were recorded on the stated date
> and have not been reverified for this publication.

Implemented in the local Android app and the website's breach-result path.

| Area | Result |
| --- | --- |
| Reliable outcomes | Website email reports distinguish found, no match, incomplete and unavailable. Coverage and retry remain visible, including in saved notes and exports. Failed or malformed provider responses cannot produce a clean result or enter the complete-result cache. Android DNS reports distinguish unanswered queries from confirmed empty records, including their derived SPF/DMARC findings. |
| Monitoring | Catalogue alerts, watched email checks and watched handles have independent scheduling and cancellation. Persistent rotation reaches every watch. Each item shows its last attempt, last successful check, coverage and retry action. Partial handle checks retain per-site baselines to avoid repeated false alerts. |
| Lookup continuity | Android keeps each lookup tool's draft, result and running job separate. Saved state retains drafts; complete archived reports restore previous results. Switching tools cannot replace another tool's result. |
| Saved reports | Username, Email, Domain, DNS, IP and Deep Search save complete readable and structured reports. History supports running again, sharing, deletion and comparison with the previous check of the same subject. Reports are written atomically outside preferences; legacy reports migrate without truncation. Comparison warns that changed source availability can change evidence. |
| Navigation | Android Back unwinds report comparison, report details, breach articles, QR results/camera, the guide and secondary destinations. Photo search is in Roadmap instead of a main tab. |
| Accessibility | Both themes have stronger text and button contrast. Detail rows stack at large text sizes. Headings, grouped reading order and live copy feedback improve accessibility semantics. |
| QR | Paste link, import QR screenshot, copy scanned text and copy destination are available. Screenshot decoding is local and does not require camera permission. Missing or multiple codes have explicit recovery messages. |
| Advertising | Ad failures and unavailability allow the pending action to continue. Basic lookups and repeat QR checks no longer require a full-screen ad. |

## Verification

- Website outcome tests: 8 passed, including rendered results, saved notes and exports.
- Offline backend tests: 82 passed; 2 live-provider tests intentionally excluded.
- Targeted Android unit tests: 36 passed, covering DNS outcomes, monitoring rotation and baselines, complete reports, comparisons, tool sessions, rewarded-ad outcomes and theme contrast.
- Android lint: passed with 0 errors and 43 warnings (dependency updates, compatibility and style/resource suggestions).
- Android emulator tests: 4 passed on API 36, covering 200% text, report actions and Back navigation, QR input/copy and imported screenshot decoding.
- Debug APK: `app/build/outputs/apk/debug/app-debug.apk`.

Manual TalkBack traversal and physical-device camera/photo-picker interaction have not been verified. Automated semantics and large-text checks do not replace that device review. No release was published.

The Android directory is already excluded from this repository's Git tracking. Its edits remain in the local workspace; a website-only commit will not include them.
