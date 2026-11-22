# OSINT investigation report example

Case title — Interpreting username checks in a digital footprint audit
Case reference — MYRECON-REPORT-01
Prepared by — MyRecon
Report date — 23 November 2026 (IST)
Handling — Public teaching example
Version — 1.0

Template: [MyRecon OSINT investigation report](https://www.myrecon.xyz/templates/osint-investigation-report-template.html#copy-the-template)

## 1. Scope and authorisation

MyRecon prepared this example from its published username benchmark. The question is what the public-page response and official API reference support for three selected fixtures. The scope is the recorded observations and platform-level account matches. Identifying the account owners is outside the scope of the benchmark.

## 2. Executive summary

| Question | Answer | Confidence |
|---|---|---|
| Does either GitLab check settle account presence for F10? | The HTTP-status rule indicated found and the official API reference indicated not found. See F01. | Unresolved |
| What supports the GitHub F01 and Hacker News F01 matches? | Each official API reference returned found. The public-page checks were inconclusive. See F02 and F03. | Probable for the platform-level matches |
| Can these findings link accounts to the same owner? | The fixture IDs are local to their platforms. The checks concern account presence only. | Unresolved |

## 3. Starting selectors

The selectors are GitLab F10, GitHub F01 and Hacker News F01, as recorded in the [published observations CSV](https://www.myrecon.xyz/assets/downloads/username-http-status-controls-november-2026.csv). Use platform, fixture ID and UTC run start together as the row key. Fixture IDs can repeat across platforms and across runs.

## 4. Method and tools

Use the published CSV to identify the three rows in the appendix. Compare `http_status_verdict` with `official_api_reference_verdict` and retain the recorded `http_status` value. Interpret a blank status as no HTTP status recorded. The [benchmark methods](https://www.myrecon.xyz/blog/username-search-benchmark-research.html#november-controls) describe data collection and link to the dated raw data. The times below are the recorded start times of the benchmark runs.

## 5. Findings

| Finding | Interpretation | Confidence | Evidence |
|---|---|---|---|
| F01 | GitLab F10 returned HTTP 200. The status-only rule said found and the official API reference said not found. Keep the conflicting results in the record. | Unresolved | E01 |
| F02 | The GitHub API reference returned found for F01. No status was recorded by the web check. Public-page visibility is unknown. | Probable | E02 |
| F03 | The Hacker News API reference returned found for F01. The web check recorded HTTP 419 and returned an inconclusive verdict. | Probable | E03 |

## 6. Alternative explanations

The GitLab response could be a generic success page. This example records the conflict because response status alone gives no evidence about the rendered profile. The Hacker News status shows a web request outcome from the benchmark environment. The cause remains unknown. The APIs supply platform-level evidence for F02 and F03, even with incomplete web checks.

## 7. Limitations

The three rows were selected to illustrate disagreement and incomplete evidence. The full CSV contains 600 repeated observations. Use that dataset and its methodology for aggregate counts. Web visibility can change by time and network, and the checks establish no common owner. The sample uses one source of evidence for each probable match.

## 8. Conclusions and next steps

Keep the GitLab result unresolved. For GitHub and Hacker News, record the API response as the reason for the probable platform-level match. Where the report needs public-page visibility, open the original source in an authorised check and record the time, access conditions and exact handle displayed. For a claim of shared ownership, gather separate corroboration before changing the confidence grade.

## Evidence appendix

| Evidence | Platform | Fixture | Run start (UTC) | HTTP status | Status-only verdict | API reference verdict |
|---|---|---|---|---|---|---|
| E01 | GitLab | F10 | 2026-11-01T10:38:27Z | 200 | found | not_found |
| E02 | GitHub | F01 | 2026-11-08T10:33:34Z | Blank in source | unknown | found |
| E03 | Hacker News | F01 | 2026-11-01T10:38:27Z | 419 | unknown | found |

Source: [November benchmark observations](https://www.myrecon.xyz/assets/downloads/username-http-status-controls-november-2026.csv).

Confidence scale: Confirmed requires independent corroboration. Probable uses direct evidence from one source. Possible describes a lead that needs verification. Unresolved covers conflicting or insufficient evidence.
