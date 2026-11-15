# Keyword intent and AI Overview check: November 15, 2026

Method: live Google searches (en, US) from the built-in browser on 15 November 2026,
reading the AI Overview and the first page of results for each query. No search
volumes are estimated here; Search Console remains the only volume evidence (see
`search-console-growth-2026-10-13.md` and `search-query-growth-2026-10-20.md`).

The rule behind every decision: if the AI Overview already answers the query in
full from someone else's page, a new page will earn few clicks. Build where the
Overview is missing, wrong, stale or cannot hand over the thing the searcher
wants (a file, a dated price table, a fresh fact).

## Results

| Query | AI Overview? | Fully answered? | Who ranks | Decision |
|---|---|---|---|---|
| best username search tool | Yes | Yes, lists WhatsMyName, UserSearch, Sherlock, Maigret, Blackbird; cites ShadowDragon | whatsmynameapp.us, Reddit r/OSINT, ShadowDragon, GitHub lists | No new page. The Overview calls WhatsMyName the "gold standard" days after it was archived: covered by the new WhatsMyName page |
| sherlock vs maigret | Yes, but about the fictional detectives | No | FootprintIQ, maxintel, GitHub | Existing `blog/sherlock-vs-maigret-vs-myrecon.html` already says "OSINT" in its title; linked from the new pages, no duplicate |
| whatsmyname vs sherlock | No | No | X post, Reddit, ffe4.org, Bellingcat toolkit | Covered by `whatsmyname-alternatives.html` comparison table |
| whatsmyname alternative | Yes | No: lists alternatives but does not know the project was archived on 9 Nov 2026 | Similarweb, GitHub list, Reddit | **Built** `whatsmyname-alternatives.html` (information gain: archival date, frozen 691-site dataset, CC BY-SA 4.0, what keeps working) |
| how much do osint tools cost | No | No: listicles without prices | Blackdot, Forensic OSINT, SOCRadar, Comparitech | **Built** `osint-tool-pricing.html`: 14 tools, every price read from the vendor's own page, cost per unit, cheapest and most expensive |
| maltego pricing / osint industries pricing | Yes | Yes, quoted from the vendor's own page | Vendor pages | No single-vendor price pages; both appear in the cross-vendor table instead |
| osint investigation report template | No | No: Reddit, Scribd PDFs, template.net | Reddit, Scribd, dutchosintguy | **Built** `templates/osint-investigation-report-template.html` + Markdown download |
| digital footprint audit template | No | No: marketing and social-media audit templates | Telkom University blog, LinkedIn, Slideshare | **Built** `templates/digital-footprint-audit-template.html` + CSV download |
| are username checkers accurate | Yes | Partly: "not 100% accurate", no evidence | Reddit, osinthandbook, Apify | Our original 6-of-24 measurement is the information gain; now cited from the new pages. Candidate for an answer block on `username-checker.html` later |
| osint tools near me | No | No | Reddit, YouTube, Netlas | **Skipped.** No local business or service area; a "near me" page would be a doorway page |
| myrecon | No | n/a | My Medic Recon first-aid kits dominate | Brand problem, not content. `Organization` JSON-LD with `sameAs` (GitHub, Play) already exists. Needs off-site mentions and branded links |
| myrecon osint | No | n/a | Unrelated "my recon" posts | Same as above. `site:myrecon.xyz` shows pages are indexed; the brand entity is weak |

## Pages built

- `/osint-tool-pricing.html`: transactional "cost" intent, prices checked 15 Nov 2026.
- `/whatsmyname-alternatives.html`: fresh fact the AI Overview lacks.
- `/templates/` hub with three template pages and three downloads in `/downloads/`.

Each opens with a 40 to 60 word "Short answer" block (quotable), carries FAQ
markup generated from the same visible text, and states its check date and the
fact that MyRecon publishes it. Old `/vs/whatsmyname` redirects now point to the
new WhatsMyName page instead of the `/vs/` hub.

## Prices we could not verify (left out on purpose)

Spokeo, BeenVerified and Whitepages refused automated reads; DeHashed's pricing
URL returned 404; Snusbase shows no price; Censys, Social Links, Skopenow and
ShadowDragon are quote only. Do not fill these in from review sites or AI answers.

## Maintenance

- Re-check every row of the pricing table monthly. MyRecon's own row shows the
  Black Friday price with the listed regular price; update it when the sale ends.
- The 6-of-24 figure now also appears on the WhatsMyName page and the report
  template page. If the measurement is ever revised, update those too (in
  addition to the three places noted in the AI-visibility memory).

## Measure after deploy

Compare equal 28-day windows in Search Console for: "osint tool pricing",
"how much do osint tools cost", "whatsmyname alternative", "whatsmyname shut down",
"osint report template", "digital footprint audit template". Request indexing
once per new URL; do not resubmit unchanged URLs.
