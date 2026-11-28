# Deep Review Submission Packet 03: Username Benchmark, HTTP Status Baseline & 22-Run Repeatability Study

## Custom Context Prompt (Paste into Google Deep Review)

> Please perform a strict adversarial peer review of this multi-part empirical benchmark study combining (A) a 30 September 2026 full-catalogue single-handle case study (`4ryanwalia`) with a 210 shared-address intersection, (B) a 20-run HTTP-status-only baseline across GitHub, GitLab, and Hacker News (600 paired observations), and (C) a 22-run repeatability audit of Sherlock and Maigret (660 paired observations). Scrutinize: (1) repeated-measurement clustering (non-independence of 20-22 runs on 10 fixed handles), (2) post-hoc rule fixes applied during the 30 September case study and whether disclosure adequately separates diagnostic debugging from blind evaluation, (3) HTTP 419 handling on Hacker News from GitHub Actions runners, and (4) comparability of full-catalogue vs shared-address metrics.

---

# Username Search Benchmark: Findings, Evidence and Limitations

**Author:** Aryan Walia (CEH, Founder, MyRecon)
**Published:** 1 November 2026 (Updated 28 November 2026)
**Canonical URL:** `https://www.myrecon.xyz/blog/username-search-benchmark-research.html`
**Publisher Disclosure:** Publisher-run study by MyRecon of its own engine alongside Sherlock `0.16.2`, Maigret `0.6.6`, and a separately captured public OSINTsearch preview.

## 1. Study Component A: Full-Catalogue Case Study & 210 Shared-Address Intersection (30 September 2026)

Using one owner-supplied handle (`4ryanwalia`), all three local engines ran on the same workstation on 30 September 2026 (`MyRecon 0749d334`, `Sherlock 0.16.2` commit `e40a45ec` honoring upstream exclusions SHA-256 `afe72771...`, `Maigret 0.6.6` commit `b6642744`).

### Full-Catalogue Results

| Engine | Checks | Reported Hits | Unique URLs | Duplicates | Supported | Contradicted (FP) | Unverified Leads | Unknown Checks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MyRecon | 561 | 12 | 12 | 0 | 12 | 0 | 0 | 244 |
| Sherlock | 430 | 19 | 18 | 1 | 11 | 2 | 5 | 127 |
| Maigret | 5,257 | 35 | 35 | 0 | 10 | 9 | 16 | 945 |

### Exact 210 Shared-Address Intersection

| Engine | Addresses Checked | Reported Hits | Unique URLs | Duplicates | Supported | Contradicted (FP) | Unverified Leads | Unknown Checks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MyRecon | 210 | 8 | 8 | 0 | 8 | 0 | 0 | 53 |
| Sherlock | 210 | 12 | 11 | 1 | 9 | 1 | 1 | 31 |
| Maigret | 210 | 10 | 10 | 0 | 9 | 1 | 0 | 25 |

**Critical transparency disclosure (post-hoc fixes):** An initial MyRecon run reported 13 hits including 1 contradicted RubyGems match (`fermion` resolved via numeric ID prefix), and a pre-recovery run reported 11 supported hits. General rules were updated before the final 12/12 run, and earlier outputs are retained in the archive. Because of those post-hoc fixes, Component A is explicitly classified as a documented diagnostic case study, not a blind held-out evaluation.

## 2. Study Component B: HTTP-Status-Only Baseline vs Official API Reference (20 Runs, 600 Observations, 1-21 Nov 2026)

Ten fixed handles per platform (5 real, 5 synthetic) were checked across 20 scheduled GitHub Actions runs (excluding 4 Nov, which had no qualifying run).

| Platform | Agreed with Reference | Contradicted Reference | Inconclusive |
|---|---:|---:|---:|
| GitHub | 194 | 0 | 6 |
| GitLab | 60 | 20 | 120 |
| Hacker News | 0 | 0 | 200 |

- All 20 GitLab contradictions came from 20 repeated observations of 1 fixture returning HTTP 200 despite official API absence.
- All 200 Hacker News public-page checks returned HTTP 419 in the GitHub Actions runner environment, whereas the official Firebase API returned 60 present and 140 absent observations.

## 3. Study Component C: 22-Run Tool Repeatability Audit (660 Paired Observations, 1-23 Nov 2026)

| Platform | Sherlock Disagreements | Sherlock Inconclusive | Maigret Disagreements | Maigret Inconclusive |
|---|---:|---:|---:|---:|
| GitHub | 0 | 4 | 0 | 16 |
| GitLab | 0 | 0 | 0 | 2 |
| Hacker News | 154 | 0 | 0 | 0 |

- All 154 Sherlock Hacker News disagreements represent 7 absent controls repeated across 22 runs (`7 x 22 = 154`), where bundled Sherlock rules returned native `CLAIMED` on HTTP 419 responses. Future MyRecon benchmark normalization quarantines HTTP 419 to `unknown` while preserving the native status.

## 4. Known Limitations (Self-Audit, 28 November 2026)

1. **Clustered repeated observations:** Neither the 600 HTTP-status observations nor the 660 repeatability observations are independent random handles; downstream statistical modeling must cluster by `(platform, fixture_id)`.
2. **Runner-specific network artifact:** GitHub Actions egress IPs triggered universal HTTP 419 on Hacker News HTML pages and intermittent HTTP 403 on GitHub; residential or mobile networks will yield different inconclusive rates.
3. **Unverified catalogue negatives:** In Component A, non-reported URLs across 561 to 5,257 sites were not exhaustively audited, so whole-catalogue recall cannot be estimated.
4. **Open artifacts:** `username-http-status-controls-november-2026.csv`, `username-tool-repeatability-november-2026.csv`, `username-benchmark.json`, `benchmarks.json`, and reproduction scripts are pinned in GitHub.
