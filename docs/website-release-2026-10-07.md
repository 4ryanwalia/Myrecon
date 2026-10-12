# MyRecon website consolidation, 7 October 2026

This release starts from `8aa5418f` on main, which already includes deployed Google email/Maps reviews, payments, SEO, benchmark UI and persistent offloaded username jobs. The dirty Desktop checkout and existing worktrees remain intact.

## Included source changes

- Main selector: Deep Search alongside standard tools, with mobile wrapping and query handoff.
- Guest standard lookups: real scans, first two actual finding cards, generic locked placeholders for the remainder. Nested review and career articles consume separate result-card slots. Progress, notices and derived identity summaries do not consume finding slots.
- Guest Deep Search: real investigations, returned section headings and safe source states, all finding details withheld by the API. Signed-in account entitlement checks remain required for full reports and follow actions.
- Temporary reveal receipts: random tokens, verified Firebase identity, owner binding, Deep Search entitlement, at most 30 minutes in bounded server memory. Failed and incomplete receipts retain those states. Restart or capacity eviction can expire a report earlier.
- Earlier linked-profile work from `4c46`: explicit connection evidence, owner-declared links, bounded follow trails, safe JSON and CSV exports.
- Earlier username work from `beb8`: nine reviewed adapters and source metadata, integrated with the current offload catalogue and fingerprint validation.
- Earlier selected-email checks from `9341` and Desktop rich-email work: evidence normalization, timelines, confidence/freshness labels, platform summaries, optional public profile/provider enrichment, LinkedIn reading and authenticated bounded photo fallback.
- Worker-console/status and embedded notebook-source changes from `17930d70` and `8b6107cd`, with current guest protection retained.
- Desktop discovery landing page generator, sitemap filtering and local API environment override. Existing sitemap-index/rendered-change tracking and editorial/Play availability corrections are preserved.
- Small backend referral retry and configured-secret checks from `ac05`; no Android app files changed.
- Disabled User Scanner foundation and local stdio tool source with original attribution. It remains disabled pending an explicitly authorized service integration.

## Reconciliation decisions

Most worktree commits are already ancestors of main. Generated HTML/data, stale full-file versions of config/plans/history/search, older Google lookup implementations and older marketing claims were not copied over newer source. Existing breach-story generators, payment code, benchmark matching/tooling and email frontend helpers were already present on main; their newer versions are preserved.

## Validation and deployment boundaries

Review used source comparison, internal import inspection, Python AST parsing, JavaScript syntax parsing and diff whitespace checks. No automated tests or Android builds were run. Provider website/backend build steps are part of deployment.

Live health/revision and published-asset checks confirm release identity and availability, not scan correctness. Manual checks remain required for sign-in reveal, account plan enforcement, mobile layout, interrupted scans, provider coverage and exports.

Optional OI, PDL, SerpAPI and LeakCheck enrichment require their existing enable flags and server-side credentials; absent configuration returns explicit unavailable states. Free Google reviews reuse the existing hosted connection. Public LinkedIn reading is opt-in. Running Colab sessions retain their old source; refreshed notebooks must be restarted manually. Render remains the fallback for catalogue-version mismatches.
