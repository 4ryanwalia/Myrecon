# Deep Review Submission Packet 02: WhatsMyName Frozen 690-Rule Replay (27 November 2026)

## Custom Context Prompt (Paste into Google Deep Review)

> Please perform a strict adversarial peer review of this live empirical replay of the archived WhatsMyName (`wmn-data.json`) username-detection dataset conducted 18 days after its 9 November 2026 archival. Evaluate: (1) whether the 42.2% (291/690) working-rule floor is accurately defined and bounded, (2) threats to validity from single-IP execution, desktop Chrome User-Agent, 20-second timeouts, and disabling HTTP redirects, (3) whether known-account churn vs site-template drift is cleanly separated, (4) CC BY-SA 4.0 attribution and privacy hygiene (redacting known handles from the public CSV), and (5) publisher conflict-of-interest disclosure because MyRecon is listed as an alternative.

---

# Live Replay of Frozen WhatsMyName Detection Rules (27 November 2026)

**Author:** Aryan Walia (CEH, Founder, MyRecon)
**Measurement Window:** 27 November 2026, `23:29` to `23:31` UTC (18 days after repository archival on 9 November 2026)
**Canonical URL:** `https://www.myrecon.xyz/whatsmyname-alternatives.html#how-many-whatsmyname-checks-still-work`
**Public Dataset:** `https://www.myrecon.xyz/downloads/whatsmyname-rule-replay-2026-11-27.csv` (CC BY-SA 4.0, derived from WhatsMyName Copyright (C) 2015-2026 Micah Hoffman)
**Publisher Disclosure:** MyRecon is one of the maintained alternatives discussed alongside Sherlock and Maigret, and conducted this replay.

## 1. Motivation & Context

On 9 November 2026, maintainer Micah Hoffman archived `github.com/WebBreacher/WhatsMyName` in read-only mode, leaving `wmn-data.json` frozen at 691 entries (690 active entries not marked invalid). Because numerous OSINT tools (including Blackbird and web runners such as `whatsmyname.app`) embed `wmn-data.json` directly, rule decay immediately affects downstream investigators.

## 2. Experimental Protocol

- **Universe:** All 690 entries in the final archived `wmn-data.json` not marked invalid.
- **Paired requests per site:**
  1. First handle listed in the entry's own `known` array.
  2. Deterministic synthetic control handle (`zq` + 12 hex characters).
- **Classification logic:** Each HTTP response was classified strictly using the entry's own `e_code`/`e_string` (exists) and `m_code`/`m_string` (missing) rules.
- **HTTP settings:** Single pass from one connection, desktop Chrome User-Agent, 20-second timeout, **redirects disabled** (because 64 WhatsMyName rules explicitly rely on 3xx status codes as their missing-account signal).
- **Privacy minimization:** The published per-site CSV omits the `known` handle strings while retaining every site name, outcome bucket, and observed status classification.

## 3. Results (n = 690 Active Rules)

| Outcome | Sites | Share | Interpretation |
|---|---:|---:|---|
| Rule still works | 291 | 42.2% | Known handle matched exists rule AND synthetic handle matched missing rule |
| Known account found, synthetic handle undecided | 79 | 11.4% | Positive rule still fires, but negative confirmation no longer matches |
| Rule no longer matches response | 126 | 18.3% | Site responded, but status/body matched neither exists nor missing rule |
| Rule reads known account as missing | 15 | 2.2% | Includes Instagram, where signed-out probes return uniform pages for real & synthetic handles |
| Request refused (HTTP 403 or 429) | 160 | 23.2% | WAF/bot protection or rate limiting rejected automated request |
| Site unreachable | 19 | 2.8% | DNS/TLS/connection error or >20s timeout |
| **Total** | **690** | **100.0%** | **0 synthetic handles triggered a false positive** |

## 4. Known Threats to Validity (Self-Audit, 28 November 2026)

1. **Single-network IP reputation effect:** The 160 HTTP 403/429 refusals (23.2%) reflect a single network egress and User-Agent. A residential or mobile IP could shift part of that bucket into working rules, while a datacenter IP could show higher refusal rates. Thus 42.2% is reported strictly as a measured single-network floor for 27 November 2026, not a permanent universal rate.
2. **Redirect handling trade-off:** Keeping redirects disabled preserves the 64 rules that require 3xx status codes, but can push sites that recently introduced canonical domain or trailing-slash redirects into the "Rule no longer matches" (18.3%) bucket. A two-pass follow-up should stratify redirect-dependent vs non-redirect rules separately.
3. **Account churn vs template decay:** Within the 15 "known account read as missing" entries (2.2%), some accounts may have been deleted or renamed by their owners rather than failing due to site HTML changes. Both failure modes degrade frozen rule verification.
4. **No multi-day temporal longitudinal series yet:** A single snapshot at Day +18 cannot estimate decay velocity (rules broken per month). Scheduling a monthly repeat replay using the identical harness would establish an empirical decay curve.
