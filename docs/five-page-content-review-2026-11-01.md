# Five existing pages strengthened — 1 November 2026

## Updated routes

- `/username-checker.html`: browser walkthrough, observed guest Quick report, source-review examples, guest/account/paid limits and useful next steps.
- `/vs/sherlock`: task-based Sherlock and Maigret alternatives, bounded Sherlock command example, selected historical observations and current website access limits.
- `/blog/find-your-own-old-accounts.html`: reproducible inbox queries, saved-login and connected-sign-in review, public-handle demonstration and ownership confirmation before account changes.
- `/digital-footprint-checker.html`: four-pass review, recorded-source demonstration, private worksheet, separate username/email limits and source-versus-search removal.
- `/guides/check-email-data-breach.html`: email walkthrough, observed incomplete-result demonstration, provider availability, interpretation and account-security actions.

The two discovery-page bodies now live in `frontend/content/discovery/`; their existing generator supplies matching visible and structured FAQ answers. The comparison record remains mirrored in the docs kit and frontend bundle. Existing routes and canonical URLs are retained.

## Observed demonstrations

The live browser was used without signing in. No ownership selections, linked-account checks, account recovery, credential changes or deletion were performed.

- Public publisher handle `4ryanwalia`, Quick scope: 100 platform checks, 22 reported findings, two visible result cards (Twitter / X and TikTok), 20 hidden cards. The UI showed zero user-confirmed accounts. These counts describe tool output, not independently verified accounts. Raw guest export: `/downloads/username-quick-demo-2026-11-01.json`.
- Reserved example address `myrecon-demo-20261101@example.com`, Email scope, linked-account checks off: zero named breaches returned; only one of three attempted breach sources completed. LeakCheck and XposedOrNot fallback were unavailable; XposedOrNot analytics completed. The UI labeled the result incomplete and withheld the exposure score. Raw export: `/downloads/email-breach-demo-2026-11-01.json`.
- Historical Standard examples come from `/data/username-benchmark.json`, measured 30 September 2026. GitHub returned `api_user`; Clubhouse returned HTTP 404; Gab was blocked; Reddit returned a challenge. Both MyRecon and Sherlock recorded GitHub as found. Historical results are labeled and are not presented as a new comparison run or current platform availability.

## Sources reviewed

- [Sherlock official project](https://github.com/sherlock-project/sherlock): installation, bounded site selection and CSV output. `--json` loads site data; it is not a report export switch.
- [Maigret usage](https://maigret.readthedocs.io/en/latest/usage-examples.html): interfaces, reporting and source limitations.
- [Gmail search operators](https://support.google.com/mail/answer/7190?hl=en) and [Google third-party connections](https://support.google.com/accounts/answer/13533235?hl=en): inbox exercises and the distinction between unlinking and deleting service data.
- [Google personal-information removal](https://support.google.com/websearch/answer/9673730?hl=en): search-result removal does not remove the source page.
- [HIBP FAQ](https://haveibeenpwned.com/FAQs), [XposedOrNot FAQ](https://xposedornot.com/faq) and [IANA example domains](https://www.iana.org/help/example-domains): provider coverage, verified-owner limits and the demonstration address.
- MyRecon release source: `backend/app.py`, `backend/core/plans.py`, `backend/config.py`, email lookup modules and `/pricing`.

## Verification

- `npm ci --ignore-scripts`: succeeded, zero audit vulnerabilities.
- `npm run build`: succeeded.
- `npm run test:seo`: all 33 tests passed after the build, and again after excluding unrelated generated output from this change.
- Checked one H1, valid Article/WebPage/FAQ JSON-LD, visible FAQ agreement, intact internal links and updated dates for all five routes.
- Verified download counts and source statuses against the text and all five sitemap `<lastmod>` entries.
- Browser inspection: desktop appearance and narrow effective viewport (500 CSS-pixel content width); no page-level horizontal overflow on the five pages. Wider tables remain locally scrollable.

Existing unrelated changes in the original working directory were preserved by using an isolated checkout. Search indexing, ranking, new-account recovery and completed privacy removals are outside the verified outcomes of this content update.
