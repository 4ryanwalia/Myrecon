# Search concepts the site is planned against (15 November 2026)

Goal: when someone searches for a username search tool, or asks an AI
assistant about one, MyRecon is the page that ranks and the source that gets
cited.

What on-site work can and cannot do: it makes the site eligible to rank and
safe to cite. It cannot put the site at position 1 by itself. The last
Search Console read (13 October) showed 123 impressions at an average position
of 11.3, with 15 pages indexed. Ranking for "username search" and getting into
AI answers both depend mostly on off-site signals: links, mentions, and the
lists and community threads that AI answers actually cite (see
`BACKLINK-STRATEGY.md` section 2). The on-site work below removes the reasons
not to rank.

Measure with:

```bash
cd frontend && npm run audit:seo
```

`--json` gives machine output. `--gsc <Queries.csv>` adds the striking-distance
report from a Search Console export. The script never edits pages.

## The ten terms

### 1. Query fan-out
**What it is.** An AI search splits one question ("best free username search
tool") into several background searches ("free username checker no signup",
"username search accuracy", "is username search legal", "sherlock
alternative"), reads the results, and writes one answer.

**How we stand.** Good. 166 of 187 long pages have question-shaped H2s and 96
carry FAQPage markup, so each sub-question has a self-contained answer to
retrieve. The sub-questions around the core query already have pages:
accuracy (`guides/why-username-checkers-report-fake-accounts.html`), legality
(`is-myrecon-legit.html`), alternatives (`/vs/`), method
(`username-sweep-vs-deep-search.html`).

**Rule going forward.** One clear question per H2, answered in the first
sentence or two under it. The audit counts "slow answers" (first paragraph
over 70 words) per page.

### 2. Information gain
**What it is.** How much a page adds beyond what already ranks. A tenth
"what is OSINT" article adds nothing; a measured result nobody else has
published adds a lot.

**How we stand.** The site has real original data: the 24-platform
false-positive measurement (6 Sep 2026) and the 35-control study against
Sherlock and Maigret (1 Nov 2026), both with downloadable evidence. Until
today only the first was marked up as a `Dataset`.

**Done 15 Nov.** The 35-control study now emits `Dataset` JSON-LD (what was
measured, when, how, and links to the CSV and JSON files). This is opt-in
through a `dataset` object in the article's front matter; see
`frontend/scripts/dataset-schema.js`. A license is emitted only when stated,
and none is stated for this study yet.

**Rule.** New research gets a `dataset` block. Pages that restate what
already ranks do not get written.

### 3. Keyword cannibalisation
**What it is.** Several of your own pages compete for the same query. Google
picks one, often not the one you want, and ranking signals are split between
them.

**How we stand. This is the biggest on-site problem.** Pages whose title
targets each head query:

| Query | Competing pages |
|---|---:|
| reverse username lookup | 4 |
| best username search tools | 4 real (14 loose matches) |
| instagram username search | 7 |
| digital footprint checker | 6 |
| username search / checker | 4 real (11 loose matches) |

Plus one exact duplicate: `blog/top-10-osint-tools.html` and
`guides/top-10-osint-tools-2026` share a title topic and nearly the same
headings.

**Applied 15 Nov** for reverse lookup, best tools, top 10 and footprint. See
"Consolidation" below.

### 4. Crawl budget
**What it is.** How many of your URLs Googlebot fetches in a given time. A
small, new domain gets a small budget, so every fetch spent on a redirect, a
duplicate or a dead link is a fetch not spent on a page that matters.

**How we stand. Clean.** 0 sitemap URLs redirect, 0 canonicals redirect, 0
internal links spend a hop on any of the 680 Vercel redirects, 0 orphans, 0
pages with only one inbound link. The one "unresolved link" the audit lists is
a JavaScript string in a script, not a real link. `sitemap-index.xml` and
`sitemap_index.xml` are identical on purpose (both names have been submitted).

### 5. Index bloat
**What it is.** Low-value URLs filling the index, which lowers Google's
opinion of the whole site.

**How we stand.** 325 indexable URLs; 0 duplicate titles or descriptions.
15 thin pages (under 300 words of main content): `badge.html`,
`osint-cheat-sheet.html`, `/videos/` and **12 video watch pages at 127 to 138
words each**. The watch pages exist so the 32-second videos can be indexed as
videos (Google only indexes a video when it is the main content of its page).
That benefit has a cost: twelve near-empty pages.

**Options (needs a decision).** Either keep them and add a real written
walkthrough to each (300+ words), or noindex them and let the hub carry the
videos, which gives up video rich results.

### 6. Striking distance
**What it is.** Queries where you rank 11 to 20, one push from page one.
Cheapest wins in SEO.

**How we stand. Cannot be measured from what is on disk.** The 13 October
export has 14 visible queries at 1 to 3 impressions each, which is too little
to rewrite anything for. The audit reads a fresh export:

1. Search Console, Performance, last 3 months, Queries tab, Export, CSV.
2. `npm run audit:seo -- --gsc path/to/Queries.csv`

Rows under 10 impressions are flagged as not enough evidence.

### 7. Passage ranking
**What it is.** Google can rank one section of a long page on its own, for a
query the page as a whole is not about.

**How we stand. Fixed 15 Nov.** Before: 36 of 187 long pages had no H2 with
an id, and only 2 had every H2 anchored. A section without an id cannot be
linked to, shared or cited on its own. After: 186 of 187 fully anchored.
The new build step `frontend/scripts/anchor-headings.js` runs last in
`build-site.js`, gives every H2 inside `<main>` a slug id, keeps existing ids,
and changes nothing on a second run. It skips the hand-authored homepage.

### 8. Site reputation abuse
**What it is.** Third-party content hosted on a strong domain to borrow its
ranking (coupon sections, paid guest posts). Google penalises the host.

**How we stand. Not applicable.** No sponsored links, no guest authors, no
third-party sections. Every author in markup is MyRecon. The audit re-checks
this on every run. Keep it that way: no paid posts, no affiliate coupon pages.

### 9. Entity salience
**What it is.** How central a named thing (person, brand, product) is to a
page. Search engines and AI models need to recognise "MyRecon" as one entity:
the tool, its makers, its other profiles.

**How we stand. Good.** All key pages name MyRecon in the title and first
paragraph and carry `Organization` markup; the homepage adds `WebApplication`.
The one weak spot is `reverse-username-lookup.html`, whose first paragraph
does not name MyRecon. Homepage `sameAs` lists the GitHub repo and the Play
listing only. Add the official social profiles to `sameAs` once they are live
and posting, and not before: an empty profile linked as "the same entity"
does more harm than good.

H1s that are the query rather than the brand ("Username search across 100+
platforms") are correct, and the brand in the title covers salience.

### 10. Generative engine optimisation (GEO)
**What it is.** Making pages easy for AI answers to retrieve, trust and cite.

**How we stand.** `llms.txt` exists and is linked from `robots.txt`; all
major AI crawlers are allowed. 47 long pages contain a dated fact; 2 carry
Dataset markup. The levers that matter, in order:

1. Original, dated numbers (the two studies). Cited because no one else has them.
2. Self-contained answers under question H2s (terms 1 and 7).
3. Being named in the lists and threads that AI answers draw on. This is
   off-site and outweighs everything above.

**Never:** hidden text or instructions aimed at AI models. It does not work,
it gets the domain demoted, and it contradicts the site's no-overclaiming
position.

## Consolidation (applied 15 November 2026, user approved)

Five pages were merged into the page that owns each query. Each source is
deleted (generated page and `content/blog/` source), listed in
`frontend/content/editorial-redirects.json`, and 301-redirected in
`vercel.json` under both the clean and `.html` route. `finalize-editorial.js`
repoints every internal link at build time, so no link spends a hop.

| Merged page | Into | Content carried over |
|---|---|---|
| `blog/reverse-username-search.html` | `/reverse-username-lookup.html` | "Worked example: a reused hobby handle" |
| `blog/reverse-username-lookup-guide.html` | `/reverse-username-lookup.html` | "How do you corroborate a username match?" |
| `blog/best-osint-tools-username-search-comparison.html` | `blog/best-username-search-tools.html` | nothing new (tool roles already covered there and on `/vs/`) |
| `blog/top-10-osint-tools.html` | `/guides/top-10-osint-tools-2026` | nothing new; footer link repointed |
| `blog/digital-footprint-checker-guide.html` | `/digital-footprint-checker.html` | "Search for yourself, then opt out of data brokers" |

The videos for the two merged posts with videos (`reverse-username-search`,
`top-10-osint-tools`) stay; their watch pages now link to the merge target.
`guides/best-username-osint-tools-2027` was merged separately by another
session into `blog/best-username-search-apps.html`.

Still open: the Instagram cluster (7 pages) needs its `guides/instagram-*`
pages retitled to narrower intents, and the homepage title still carries
"Digital Footprint Checker" next to `/digital-footprint-checker.html`. Both
are retitles, not merges; the homepage one should wait for fresh Search
Console data because the homepage earns almost all current clicks.

After deploy: request indexing for the three target pages in URL Inspection.
Expect the merged URLs to drop out of the index over a few weeks.
