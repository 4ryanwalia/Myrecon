# Measure actual recommendations

Keep the 25 questions in `questions.json` stable: 20 unbranded discovery questions and five branded accuracy checks. Each has a fixed search instruction. There are five batches of four unbranded questions and one branded question. Run one batch each week on ChatGPT, Gemini and Claude; this covers the full panel every five weeks. A full-panel run can also be made after a material product or content change. Preserve a versioned question snapshot inside each run.

## Run a sample

From the repository root:

```powershell
python tools/recommendation_benchmark.py plan 2026-11-02-weekly --batch 1
python tools/recommendation_benchmark.py report measurement-data/recommendations/runs/2026-11-02-weekly.json
```

Omit `--batch` to create all 75 question/assistant cells. The planner refuses to overwrite an existing run. Keep observations, transcripts, screenshots and analytics exports in the gitignored `measurement-data/recommendations/` directory. These contain operational and account-specific data and stay local. The public repository contains the question panel, protocol and instrumentation.

1. Open a fresh consumer-product chat for each question, outside projects and custom agents. Prefer ChatGPT logged out or temporary chat, Gemini temporary chat and Claude incognito. Do not paste product documentation, previous answers or this repository into the test chat. Do not ask follow-up questions before saving the first answer.
2. Enable web search where a control exists. Send the exact saved prompt, including its search instruction, and verify completion. Record visible search activity separately from search availability. The ChatGPT documentation describes search activity and citations in [Web search](https://learn.chatgpt.com/docs/web-search).
3. Record timestamp with offset, visible model label, account mode, language, operator region, fresh-session status and search status. If the model version is not exposed, write `default; exact model not exposed`. A fresh conversation can still receive account customization: record any visible personalization and do not call these neutral or representative sessions.
4. Save the response text, conversation URL and screenshot. Capture citation destinations and source titles, preserving exact URLs; store direct recommendation/answer links separately. An answer link is not automatically a supporting citation. Use `citation_capture=partial` when any destination remains unextracted; never invent a URL from a source title. Normalize hostnames only in derived summaries, preserving raw URLs in the log.
5. Set `mentioned=true` only when the answer identifies this MyRecon product. Set `recommended=true` only for an affirmative suggestion to use it; a passing mention, warning or comparison is insufficient. Keep branded and unbranded denominators separate. In a branded answer, a mention is expected and is not discovery evidence.
6. For each MyRecon inaccuracy, preserve the claim, correction, severity, live evidence URL and review date. Check current plans, product interfaces and first-party documentation. Missing coverage is a content gap, not automatically a false statement. If nothing was checked, use `not_reviewed`, rather than `no_issues_found`. Keep competitor-claim review separate.
7. Record login requirements, assistant errors, rate limits, interrupted answers and unavailable search with their own statuses and null outcomes. Preserve every attempted response, including errors. A retry gets another `attempt` number and a fresh chat; the report uses the first successful attempt per question/assistant. Never retry until a preferred recommendation appears.

Use `not_run` for an unattempted cell. A login/access check does not constitute 25 attempted questions. Summaries show counts and denominators, missingness and settings. Small rotating batches, model changes, search-index changes, location, time and account context prevent broad ranking or causal claims. Compare identical questions and comparable settings when looking for changes; run a separately labeled repeat batch if apparent changes matter.

## Visits, completed scans and new signups

The website's Google Analytics tag uses measurement ID `G-3L8YYC6NKF`. The connected MyRecon GA4 property is `556131397` in account `409665744`. Use the selected property's reporting timezone for traffic windows, and record it alongside the ISO capture timestamp; it may differ from the operator's Asia/Kolkata timezone. Keep reporting windows consistent and end historical windows on a complete day.

The referral module emits:

| Event | Meaning | Useful breakdowns |
|---|---|---|
| `ai_referred_visit` | A recognized AI entrance, deduplicated within a tab across internal navigation | `ai_source`, `attribution_method` |
| `scan_complete` | A new lookup reached its terminal result | `ai_source`, `scan_tool`, `scan_scope`, `scan_outcome` |
| `sign_up` | Firebase explicitly returned `isNewUser=true` for a completed Google sign-in | `ai_source`, `attribution_method`, built-in `method` |

Recognized referral hosts are `chatgpt.com`, `chat.openai.com`, `gemini.google.com` and `claude.ai`. Exact allowlisted source tags can also attribute visits, labeled `utm`. Attribution survives same-tab internal navigation for a 30-minute activity window; another external source replaces it. Restoring auth state, returning-user logins, reopening saved scans and revealing retained reports do not emit new signup or scan-completion conversions. Streams that fail before their terminal response do not emit a completion. Partial terminal responses have `scan_outcome=partial`.

Report username, email and Deep Search separately; other tool completions are also identifiable by `scan_tool`. Count **completed** scans with `scan_outcome=complete`; show partial outcomes alongside them. Scan events are counts, so one visitor can complete multiple scans. `ai_referred_visit` is a tab/window entrance measure, not a replacement for GA4's native Sessions metric. A funnel conversion rate requires session/user deduplication in an exploration; do not divide arbitrary event counts and label the result a user conversion rate.

The module sends only fixed source/tool/status categories and the page URL without its query or fragment. It does not send lookup values, result contents, email addresses or account IDs. Signup confirmation follows Firebase's [AdditionalUserInfo.isNewUser](https://firebase.google.com/docs/reference/js/auth.additionaluserinfo).

During setup, register these five event-scoped custom dimensions: `ai_source`, `attribution_method`, `scan_tool`, `scan_scope`, `scan_outcome`. See Google's [custom-dimension instructions](https://support.google.com/analytics/answer/14239696?hl=en). Registration was verified on 2026-11-01. Reporting can take 24–48 hours after collection and registration; configuration is not proof of received conversion data. Do not backfill historical scan/sign-up counts from page views or all-key-event totals.

For each assistant and traffic window, record native GA4 sessions with recognized session source/medium, attributed entrance events, complete scan events, partial scan events and new signups. Preserve the report/export URL, property, window, timezone, filters, observed counts and collection-status caveats. Missing historical instrumentation or pending data is `null`, not zero. Visit evidence does not tie an individual visitor to a benchmark question.

Use `?mr_benchmark=1` before operator tests on MyRecon. This suppresses module events and the tag's automatic page view in that tab for 30 minutes, including internal pages. It does not promise to suppress every unrelated third-party script. Test event emission locally with a stub collector; do not create production signups or pretend that test scan events are real conversions. Plain HTTP source checks do not execute analytics scripts.

Referrers and tags are attributable signals, not proof that an assistant recommended the product. Apps can omit referrers, copied links can appear as direct visits, tags can be reused, and consent/ad blockers reduce collection. Leave such visits unattributed. Keep the response samples and business outcomes side by side without claiming that one caused the other.

## Recurring review

The weekly review should rotate batches 1–5, append results and traffic evidence, regenerate the report and preserve failed attempts. Resume an unfinished baseline before advancing the rotation. Verify logged-in access and search availability each run. Notify on meaningful findings, errors, completed sampling batches or required action; avoid unchanged-status notifications. Never fabricate responses with an API or ordinary search result when a consumer assistant is unavailable.
