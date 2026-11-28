# Google Deep Review Submission Packets (MyRecon Flagship Empirical Studies)

**Prepared:** 28 November 2026
**Author / Reviewer:** Aryan Walia (CEH, Founder, MyRecon)
**Target portal:** `https://research.google/deepreview/` (Google Research Deep Review, powered by Gemini 4 Argon; 2 free reviews/week with a Google Account or higher volume via a Gemini API key against `deepreview.googleapis.com`)

## What Google Deep Review Is (and Is Not)

Google Deep Review is Google Research's public multi-agent document verification and peer-review system (evolved from the Paper Assistant Tool / PAT). It is **not** a Google Search ranking console. Its four-stage pipeline:

1. **Document Segmentation** (breaks the manuscript into verifiable claims, tables, methods, and citations)
2. **Adaptive Compute Budgeting** (allocates deeper reasoning to statistical tables, methodology flaws, and high-risk claims)
3. **Deep Parallel Verification** (audits logical soundness, technical accuracy, evidence grounding, missing context, internal cross-section consistency, and clarity)
4. **Global Synthesis & Agentic Web/Literature Grounding** (cross-checks external references and flags contradictions or unsupported generalizations)

Submitting MyRecon's four original empirical studies to Google Deep Review strengthens their scientific rigor, catches subtle methodological or statistical weaknesses before external researchers or journalists cite them, and turns MyRecon's research hub into genuinely citable primary literature (the highest-leverage driver of E-E-A-T, editorial backlinks, and AI Overview citations).

## Submission Schedule (Respecting the 2 Free Reviews/Week Quota)

| Week | Packet File | Live URL | Review Focus |
|---|---|---|---|
| Week 1 | [01-controlled-study-35-controls-2026-11-01.md](./01-controlled-study-35-controls-2026-11-01.md) | `https://www.myrecon.xyz/blog/username-search-controlled-study-2026.html` | Pre-registered 35-control evaluation (MyRecon, Sherlock, Maigret), Clopper-Pearson bounds, shared-API coupling |
| Week 1 | [02-whatsmyname-690-rule-replay-2026-11-27.md](./02-whatsmyname-690-rule-replay-2026-11-27.md) | `https://www.myrecon.xyz/whatsmyname-alternatives.html` | 27 Nov 2026 live replay of all 690 archived WhatsMyName rules (42.2% working floor), single-network & redirect validity |
| Week 2 | [03-username-benchmark-and-http-status-2026-11.md](./03-username-benchmark-and-http-status-2026-11.md) | `https://www.myrecon.xyz/blog/username-search-benchmark-research.html` | 30 Sep single-handle case study, 210 shared-address intersection, 20-run HTTP 200 dataset (600 obs), 22-run repeatability (660 obs) |
| Week 2 | [04-false-positive-24-platform-measurement-2026-09-06.md](./04-false-positive-24-platform-measurement-2026-09-06.md) | `https://www.myrecon.xyz/guides/why-username-checkers-report-fake-accounts.html` | 6 Sep 2026 24-platform paired-request byte measurement & scoring tautology proof |

## How to Submit Each Packet

1. Open `https://research.google/deepreview/` in your signed-in Google browser.
2. Upload (or export to PDF and upload) the Markdown dossier below.
3. Copy the **Custom Context Prompt** at the top of each packet into Deep Review's context / instructions field so the review agents focus specifically on statistical soundness, OSINT methodology, publisher conflict-of-interest disclosure, and reproducibility.
4. Save the Deep Review report and incorporate any valid methodological critiques directly into the corresponding page's `Methodology review and limitations` section (dated with the revision date), never hiding or softening a valid limitation.
