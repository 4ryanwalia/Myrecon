# Google generative AI impressions: baseline, 24 Nov 2026

Source: Search Console > Generative AI report (`/performance/search-analytics/ai`),
property `sc-domain:myrecon.xyz`, read 24 Nov 2026. Data ends 22 Nov (about a two-day lag).
The report has no query breakdown. It shows only pages, countries, devices and days.

## The trend is up, not down

| Period | AI impressions |
|---|---|
| Aug 23 to Sep 28 | 2 |
| Sep 29 to Oct 19 | 26 |
| Oct 20 to Oct 26 | 57 |
| Oct 27 to Nov 2 | 73 |
| Nov 3 to Nov 9 | 63 |
| Nov 10 to Nov 16 | 77 |
| Nov 17 to Nov 22 (6 days) | 139 |
| Last 28 days | 366 |
| Last 3 months | 437 |

Best days: 17 Nov (35), 19 Nov (34) and 20 Nov (31). 22 Nov shows 3 because the day is
still filling in, and "today" always shows 0. Read the data at least three days after the
day you are checking.

## Which pages get AI impressions (28 days)

Homepage 106, /blog/best-data-breach-checkers 35, /find/github-profile 26,
/blog/account-deletion-vs-deactivation 22, /find/instagram-account 21,
/osint-tool-pricing 19, /blog/instagram-username-search 13, /blog/best-sherlock-alternatives 12.
69 pages had at least one.

The pattern: a page appears in AI answers only once it ranks on page 1 or 2 in normal
search. Each cited page averages position 6 to 21. Pages with many normal impressions but
position 40 to 75 (/free-osint-tool, /blog/best-free-osint-tools-for-investigators,
/blog/best-osint-tools-username-search-comparison, /username-checker) get almost none.
The ceiling is ranking, not markup.

best-data-breach-checkers ranks 1 to 5 for long, conversational questions ("which
platforms notify users of recent data leaks?", "which consumer apps keep watch for stolen
passwords?"). A page built as a direct answer to a "which / how / is" question gets cited.

## Changed on 24 Nov 2026

Two pages had a real query with no matching section:

- `/blog/instagram-osint-public-profile-guide.html`: new H2 "Can OSINT see a private
  Instagram account?" with a direct answer. Query "osint instagram private account":
  14 impressions, position 30.4.
- `/blog/account-deletion-vs-deactivation.html`: "What a deletion request can do" is now
  "How long is data kept after you delete an account?", opening with an answer built only
  from the vendor-sourced table on the page. Query "account deletion and retention":
  10 impressions, position 64.1.

Already answer-first, so left alone: /find/github-profile (reworked 23 Nov),
/blog/instagram-username-search, /blog/best-data-breach-checkers, the homepage.
/vs/sherlock's 139 impressions are for a different product (sherlock.xyz).

## Re-check on or after 22 Dec 2026

Compare the weekly totals above, and the position of those two queries. Off-site mentions
(lists, Reddit, GitHub awesome-lists) still matter more than on-site work. See
`docs/ai-citation-check-2026-11-18.md`.
