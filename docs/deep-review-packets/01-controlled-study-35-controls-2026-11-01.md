# Deep Review Submission Packet 01: Controlled Username Search Study (35 Controls, 8 Platforms, 3 Tools)

## Custom Context Prompt (Paste into Google Deep Review)

> Please perform a strict adversarial peer review of this empirical OSINT measurement study conducted and published by the developer of one of the evaluated tools (MyRecon). Focus on: (1) denominator arithmetic and scoring definitions across all 35 controls, (2) statistical power and small-sample confidence bounds on zero-observed-error claims, (3) shared-API coupling between the independent reference oracle and the publisher's engine, (4) fairness of honoring Sherlock's upstream exclusion list while scoring coverage, and (5) any remaining claims that overreach the 8-platform developer/community sample. Recommend concrete methodological improvements for a follow-up study.

---

# Expanded Username Testing: 35 Platform-Specific Controls Across Eight Platforms

**Author:** Aryan Walia (CEH, Founder, MyRecon)
**Published:** 1 November 2026 (Methodology review updated 28 November 2026)
**Canonical URL:** `https://www.myrecon.xyz/blog/username-search-controlled-study-2026.html`
**Observation Window:** `2026-11-01T16:39:28Z` to `2026-11-01T16:41:33Z` (UTC)
**Publisher Disclosure:** MyRecon conducted and published this evaluation of its own local web engine (`9491be66`) alongside Sherlock (`0.16.2`) and Maigret (`0.6.6`). No customer search history or personal social-media accounts were used.

## 1. Abstract & Key Findings

We evaluated three username-enumeration engines (MyRecon web engine, Sherlock 0.16.2, and Maigret 0.6.6) on a predeclared manifest of 35 platform-specific controls across eight developer and technical-community platforms (GitHub, GitLab, Hacker News, Docker Hub, Dev.to, npm, Keybase, and PyPI).

- **MyRecon (`9491be66`):** 6 supported matches (TP), 0 false positives (FP), 0 false negatives (FN), 18 supported absences (TN), 11 unresolved/unscored (Coverage: 24/35 = 68.57%; FP/scored negatives: 0/18).
- **Maigret (`0.6.6`):** 6 TP, 0 FP, 0 FN, 18 TN, 11 unresolved/unscored (Coverage: 24/35 = 68.57%; FP/scored negatives: 0/18; 2 additional native npm `CLAIMED` outputs remained unscored because the reference endpoint returned HTTP 401).
- **Sherlock (`0.16.2`):** 4 TP, 0 FP, 0 FN, 11 TN, 20 unresolved/unscored (Coverage: 15/35 = 42.86%; FP/scored negatives: 0/11; 9 controls were excluded by Sherlock's captured upstream exclusion list for Hacker News and DEV Community, and 5 denied npm HTTP 403 responses were normalized from native `AVAILABLE` to `unknown`).

## 2. Predeclared Control Manifest & Reference Oracle

- **Manifest composition (35 controls, 23 literal handle spellings / 22 case-folded strings):**
  - 11 upstream claimed fixtures (published in Sherlock/Maigret site definitions)
  - 8 upstream unclaimed fixtures
  - 16 deterministic 14-character alphanumeric negative candidates (2 per platform, derived from study ID, platform, and index)
- **Reference verification rules (executed before all tool runs):**
  - Exact typed official API objects (`api.github.com/users/{u}`, `gitlab.com/api/v4/users?username={u}`, `hacker-news.firebaseio.com/v0/user/{u}.json`, `hub.docker.com/v2/users/{u}/`, `dev.to/api/users/by_username?url={u}`, `keybase.io/_/api/1.0/user/lookup.json?username={u}`) or explicit API absence establish truth.
  - Raw HTTP 200 HTML, inter-tool agreement, login walls, and client challenges (e.g., PyPI Client Challenge across C31-C35) never establish truth and remain `reference_unresolved`.
  - All 5 npm reference requests (`registry.npmjs.org/-/user/org.couchdb.user:{u}`) returned HTTP 401 and remained `reference_unresolved` (C22-C26).
  - Keybase unclaimed fixture `noonewouldeverusethis7` (C28) returned HTTP 200 without satisfying the typed absence rule and stayed `reference_unresolved`.
  - Sherlock's historical Hacker News claimed fixture `blue` (C09) returned JSON `null` from the official API and was verified absent in this snapshot; `pg` (C10) was verified present.

## 3. Summary Tables

### Table 1: Scored Outcomes Across All 35 Controls

| Tool | TP | FP | FN | TN | Unresolved / Unscored | Scored / Total | Coverage | FP / Scored Negatives |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MyRecon `9491be66` | 6 | 0 | 0 | 18 | 11 | 24 / 35 | 68.57% | 0 / 18 |
| Sherlock `0.16.2` | 4 | 0 | 0 | 11 | 20 | 15 / 35 | 42.86% | 0 / 11 |
| Maigret `0.6.6` | 6 | 0 | 0 | 18 | 11 | 24 / 35 | 68.57% | 0 / 18 |

### Table 2: Native Claims Retained Before Normalization

| Tool | Reported Native Claims | Source Supported | Source Contradicted | Reference Unresolved | Unknown Predictions |
|---|---:|---:|---:|---:|---:|
| MyRecon | 6 | 6 | 0 | 0 | 10 |
| Sherlock | 4 | 4 | 0 | 0 | 14 |
| Maigret | 8 | 6 | 0 | 2 | 5 |

## 4. Pinned Revisions & Execution Environment

- **Runtime:** Python 3.12.14, Requests 2.34.2, single Windows workstation and network, sequential execution (reference -> MyRecon -> Sherlock -> Maigret), 1 connection, no retries, no credentials, no proxies or block bypass.
- **MyRecon commit:** `9491be6683cfd329a33e6c38682a7bc83a81032f` (rule hash `1c58ba2291268402aa1ac2801d9ce31aeea7fba492a90742343eedf2949f06b6`)
- **Sherlock 0.16.2 commit:** `e40a45ec2a074b90703b3b4b842c8a3adbd6ada3` (rule hash `fcc608f68c2c017993e5612056686509554f779b3c499cca9407c5d5d5b6b244`)
- **Maigret 0.6.6 commit:** `b6642744988e7e6c2d21f75db60ec3093019ba25` (rule hash `e12b50a3a08894710e2f98264ad48ab8fcfdfbe0e46bc35c2a3846b2c74de364`)
- **Open Artifacts:** `evidence.zip`, `checks.csv` (105 rows), `study.json`, `controls.json`, `SHA256SUMS.txt` published on the study page and pinned in GitHub commit `24b7deb129966b54297e9d8777d274c73d128925`.

## 5. Known Methodological Limitations (Self-Audit, 28 November 2026)

1. **Small-sample statistical uncertainty:** Zero false positives out of 18 scored negatives yields an exact 95% Clopper-Pearson upper bound of 18.5% (and 28.5% for 0/11 on Sherlock). This sample cannot prove a "0% false positive rate" across 560+ sites.
2. **Oracle-engine coupling:** MyRecon and the reference verifier query overlapping official REST endpoints on GitHub, GitLab, Hacker News, Docker Hub, and Dev.to. Agreement measures regression consistency rather than independent ground truth on closed web platforms.
3. **Platform-domain bias:** All eight platforms are developer/community services with relatively clean APIs. Consumer social networks (Instagram, TikTok, X, Snapchat) exhibit much higher login-wall and anti-bot refusal rates.
4. **Upstream fixtures are not held-out blind controls:** Upstream claimed fixtures are known to Sherlock/Maigret maintainers; a future phase should add freshly created, owner-verified test accounts across consumer and developer networks.
