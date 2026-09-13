# Backlink strategy — myrecon.xyz

Written for this site specifically: a free, keyless OSINT lookup tool plus an
18-guide library, a generated breach archive, an Android app, and a paid
footprint-removal service, run by a named penetration tester.

**Link status legend.** Every URL below returned a live response when this was
written. `[403]` means the host blocks automated requests — the page is real
but could not be fetched here, so open it in a browser first. Nothing in this
file asserts that a site accepts guest posts, pays for links, or will accept a
submission. Where that matters it says **verify before outreach**.

**Two rules that override everything else here.** Do not invent a relationship
that does not exist, and do not pitch the tool where the community's rules
forbid self-promotion. Both get the domain a reputation that costs more than
any link is worth.

---

## 1. What this site can actually earn links with

Most tool sites have nothing to link *to* except the tool, which is why most
tool sites never earn links. This one has three genuine assets:

1. **Original measurement.** `/guides/why-username-checkers-report-fake-accounts.html`
   contains something almost nothing else in this niche has: a measurement of
   what 24 platforms return for a real handle versus an invented one, with the
   finding that several are byte-for-byte identical. That is a citable claim
   with data behind it.
2. **A methodology position.** The site's whole argument is that OSINT tools
   report unverified findings as facts, and it refuses to do so — name search
   is deliberately not offered on Deep Search because handles guessed from a
   name return whoever registered them. Refusing a feature everyone else ships
   is a story.
3. **A maintained breach archive** that rebuilds from HIBP daily, with a
   severity model and a plain-English account of what each leaked field costs
   the person it belongs to.

Lead with those. The tool is the call to action, not the pitch.

---

## 2. Named targets

### Tool directories and curated lists

| # | Target | Why it fits | Angle |
|---|---|---|---|
| 1 | [OSINT Framework](https://osintframework.com) | The canonical OSINT tool tree; a link here is the single most on-topic link available in this niche. | Submit under username/email/domain. Contributions go through its GitHub repo — check the current submission route in the repo README, it has changed before. |
| 2 | [jivoi/awesome-osint](https://github.com/jivoi/awesome-osint) | The most-forked OSINT awesome-list. Inclusion propagates to dozens of mirrors and static site builds. | PR adding MyRecon under username/email. Read CONTRIBUTING first — awesome-lists reject entries that read as marketing. One line, factual. |
| 3 | [Ph055a/OSINT-Collection](https://github.com/Ph055a/OSINT-Collection) | A second widely-forked collection with a different maintainer and audience. | Same PR, written for that list's format. |
| 4 | [github.com/topics/osint](https://github.com/topics/osint) and [osint-tool](https://github.com/topics/osint-tool) | Topic pages are how people browse for tools on GitHub. | Not outreach — tag the public repo correctly so it appears. Free and immediate. |
| 5 | [IntelTechniques tools](https://inteltechniques.com/tools/) | Michael Bazzell's tool set, heavily used by working investigators. High authority, small and curated. | **Verify before outreach.** Check whether he takes submissions at all; he has historically been selective. Do not pitch without reading the page first. |
| 6 | [OSINT Dojo](https://osintdojo.github.io/) | Training-oriented resource collection aimed at beginners — matches the guide library more than the tool. | Offer the guides as a learning resource, not the tool as a product. |
| 7 | [AlternativeTo](https://alternativeto.net) `[403]` | Ranks for "alternative to X" queries, which is exactly how people find a free tool when a paid one disappoints. | Create the listing, then list it as an alternative to the paid username-search products. Community-moderated — a thin listing gets removed. |
| 8 | [SaaSHub](https://www.saashub.com) | Software directory with real crawl depth and an alternatives structure. | Straight listing. Low effort, low-to-moderate value. |
| 9 | [OpenAlternative](https://openalternative.co) | Indexes open-source alternatives to commercial software. | **Verify eligibility first** — it requires a genuinely open-source project. Only pursue if the repo licence qualifies. |
| 10 | [Product Hunt](https://www.producthunt.com/topics/security) | A launch gets a permanent listing plus a burst of the secondary coverage that becomes real links. | Launch the *Android app* rather than the website — a phone app is a cleaner PH story than a web tool, and the on-device angle is the hook. One launch, done properly, beats three half-hearted ones. |

### Communities

Links from these are usually nofollowed. Pursue them for the traffic, the
secondary pickup, and the feedback — not for PageRank.

| # | Target | Why it fits | Angle |
|---|---|---|---|
| 11 | [r/OSINT](https://www.reddit.com/r/OSINT/) `[403]` | The practitioner audience, and the exact people who have been burned by false positives. | **Read the self-promotion rules first and follow them exactly.** The post that works is the false-positive measurement as a finding, with the tool mentioned as how it was measured. A "check out my tool" post gets removed. |
| 12 | [r/privacy](https://www.reddit.com/r/privacy/) `[403]` | Matches the footprint-reduction guides and the removal service. | Share the data-broker and digital-footprint guides. Same rule: contribute the content, not the URL. |
| 13 | [Hacker News](https://news.ycombinator.com) | A Show HN that lands produces links for years. | Show HN framed on the engineering decision: why the tool refuses to report a match it cannot verify, and what measuring 24 platforms showed. HN rewards the honest negative result and punishes the product pitch. |
| 14 | [Week in OSINT](https://sector035.nl) | A long-running OSINT newsletter that rounds up tools and findings weekly — a standing, repeatable slot. | **Verify current submission method before contacting.** Send the measurement piece, not a launch announcement. |
| 15 | [OSINTMe](https://osintme.com) | Independent practitioner blog covering tooling and technique. | **Verify before outreach** — do not assume guest posts are accepted. A tool tip or a link to the measurement is the realistic ask. |
| 16 | [dev.to](https://dev.to) / [Hashnode](https://hashnode.com) | Self-publishing with a real audience. Canonical tags let you republish without a duplicate-content problem. | Republish one guide with `rel=canonical` pointing back here. Never republish without the canonical. |

### Resource-page and citation targets

| # | Target | Why it fits | Angle |
|---|---|---|---|
| 17 | University and library "digital privacy" / "media literacy" guides | These pages link to free explainer resources constantly, and `.edu` links carry weight. | Search `site:.edu "digital footprint" resources` and `site:.edu "OSINT" guide`. Pitch the guide, not the tool. This is slow and has the best yield per link of anything on this list. |
| 18 | Journalism and fact-checking training resources, e.g. [Bellingcat's resources](https://www.bellingcat.com/resources/) | Verification is the site's actual argument, and it is Bellingcat's entire subject. | **Verify before outreach.** Realistically this is earned by the measurement piece being good enough to cite, not by asking. Treat it as the target the linkable asset aims at. |
| 19 | [Trace Labs](https://www.tracelabs.org) `[403]` | Runs OSINT CTFs for missing-persons work; participants need verification-discipline material. | Offer the verification guide as a participant resource. **Verify before outreach** — do not claim any affiliation. |
| 20 | Security blogs that already cover breaches, e.g. [Cybernews](https://cybernews.com) `[403]` | The breach archive is directly relevant to their beat. | Not a link request. When a breach the archive covers is in the news, the archive page is a citable secondary source. Pitch the page, once, on the day it matters. |

---

## 3. Linkable assets to build

Ranked by the ratio of links earned to effort.

1. **Expand the false-positive study into a standing, dated report.** It already
   exists for 24 platforms. Take it to 100, publish the method and the raw
   per-platform results, and re-run it on a schedule with the date visible.
   A number people can cite — "on N of 100 platforms, a real and an invented
   handle are indistinguishable" — is the single most linkable thing this site
   can own, and re-running it gives a reason to be cited again each year.
2. **A breach severity methodology page.** The generator already scores every
   breach and already holds a written justification for what each leaked data
   class costs a person. That reasoning is currently spread across article
   pages. Collected into one cited page it becomes the thing people link when
   they need to explain why one breach is worse than another.
3. **"What actually happens when you ask a data broker to delete you."** A
   first-person account with dates, what was sent, what came back and what was
   still live 90 days later. Nobody publishes the follow-up, which is why the
   follow-up is what gets linked. It also feeds the removal service directly.
4. **A free annual "state of the breach year" summary** built from data the
   archive already holds: totals, which data classes appeared most, how long
   disclosure took. Journalists need a citable annual number every January.
5. **An embeddable breach-check widget** with attribution built in. Every embed
   is a link. Only worth doing after the API can take the load.

---

## 4. Ninety-day cadence

Roughly four focused hours a week. The order matters: fix the foundation, then
build the asset, then pitch it.

**Weeks 1–2 — foundation**
- Verify Search Console and Bing (see SEO-REPORT.md), submit the sitemap.
- Claim the profiles that are pure listings: GitHub topics, SaaSHub, AlternativeTo.
- Record the current linking-root-domain count so later work has a baseline.

**Weeks 3–4 — the on-topic directories**
- Submit to OSINT Framework.
- Open PRs against both awesome-lists. Expect slow review; open and move on.
- Check OpenAlternative eligibility and submit only if the licence qualifies.

**Weeks 5–8 — build the asset**
- Expand the false-positive study to 100 platforms. This is the quarter's real
  work; everything after it is distribution.
- Publish the method and the raw results alongside the conclusion.

**Weeks 9–10 — launch it**
- Show HN, framed as the finding.
- r/OSINT and r/privacy, inside each subreddit's rules.
- Send it to Week in OSINT.

**Weeks 11–12 — outreach and Product Hunt**
- Twenty `.edu` resource-page pitches, one at a time, each referencing the
  specific page it should sit on. Generic outreach is ignored.
- Launch the Android app on Product Hunt.
- Re-measure and decide what to repeat.

Then repeat the shape: one asset a quarter, distributed properly, beats
continuous low-value submission.

---

## 5. What not to do

- **Paid link networks and "guest post for $X" sellers.** This is a direct
  violation of Google's link spam policy. The sites selling them have
  footprints Google already recognises; buying in attaches this domain to a
  known bad neighbourhood.
- **PBNs.** Same thing with more steps and more money.
- **Mass directory blasts.** A hundred links from unvisited general directories
  is a spam signal, not a ranking signal. Ten on-topic listings beat all of them.
- **Reciprocal link swaps at scale.** Two unrelated sites linking each other for
  SEO is a recognised pattern.
- **Automated comment and forum posting.** Nofollowed, removed, and it burns the
  brand in the exact communities that matter here.
- **Exact-match anchor text at volume.** A backlink profile where most anchors
  say "free OSINT tool" looks bought, because it is how bought links look. Let
  anchors be the brand, the URL, or the natural phrase.
- **Pitching the removal service into privacy communities.** These communities
  are hostile to anything that monetises fear, and they are right to be. Lead
  with the free guides.

---

## 6. Tracking

**The only number that matters is referring domains, not total backlinks.** A
thousand links from one domain is one vote.

- **Search Console → Links** is free, is Google's own data, and is the source of
  record. Check monthly: total external links, top linking sites, top linked
  pages, and the anchor-text distribution. If one commercial anchor dominates,
  stop building that anchor.
- **Search Console → Performance**, filtered to the pages you are promoting, for
  whether links are translating into impressions and position.
- **Bing Webmaster Tools** carries its own backlink report free, with data
  Google's does not show. It also imports straight from Search Console, so it
  costs about two minutes to set up.
- **A dated spreadsheet** of every target: pitched date, outcome, link URL. This
  is what stops the same site being pitched twice and reveals which angles land.
- Ahrefs/Semrush give faster discovery and competitor comparison, but neither is
  necessary to run this plan.

Review monthly against the baseline from week 1. Judge a quarter on referring
domains gained and on whether the pages you wanted to rank moved — not on the
number of submissions sent.
