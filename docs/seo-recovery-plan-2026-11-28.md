# SEO recovery plan, 28 Nov 2026

Read from Search Console (property `sc-domain:myrecon.xyz`), live Google results and Google Ads Keyword Planner on 28 Nov 2026. No paid tools.

## 1. What happened

| Period | Impressions per day | Clicks per day | Avg position |
|---|---|---|---|
| 1 to 19 Nov | 150 to 300 | 4 to 12 | 20 to 28 |
| 20 to 23 Nov | 259, 148, 121, 96 | 5 to 12 | 30 to 42 |
| 24 to 25 Nov | 4 and 13 | 1 | 66 to 68 |
| last 24 h (26 to 27 Nov) | 28 | 1 | 55.5 |

- This is a real drop, not data lag. Nov 24 still read 4 impressions four days later.
- **Google's November 2026 core update** started 10 Nov and ran 13 days 20 hours, so it finished about 24 Nov (Search Status Dashboard). The drop lands on the last days of the rollout. The dashboard also preannounced a **December 2026 core update** on 24 Nov.
- **Not technical.** Pages return 200 and carry `index, follow`. Canonicals are correct and robots.txt is fine. `site:` still lists the pages. GSC shows 254 pages indexed and no manual action.
- **Site-wide.** Pages whose titles never changed also collapsed:

| Page | 5 to 19 Nov | 21 to 27 Nov |
|---|---|---|
| instagram-username-search | 94 | 0 |
| how-to-find-someones-social-media-accounts | 24 | 0 |
| account-deletion-vs-deactivation | 101 | 14 |

- **Churn made it worse.**
  - 102 commits since 19 Nov.
  - 21 of the 34 pages that had 15 or more impressions were retitled after 19 Nov.
  - Every retitle restarts Google's evaluation of that page.
- **Where the old impressions came from.** Before the drop, most were long-tail queries at positions 5 to 20, plus the brand query "myrecon". Head terms never reached page 1:

| Query | Position before the drop |
|---|---|
| osint tools | ~80 |
| username search | ~80 |
| reverse username search | ~53 |
| username lookup | ~86 |

## 2. Search demand (Keyword Planner, all locations, Nov 2025 to Oct 2026)

| Monthly searches | Keywords |
|---|---|
| 10K to 100K | username search, username checker, instagram username search, reverse email lookup, email osint, osint tools, **discord id lookup**, whatsmyname, namechk, idcrawl, holehe, maigret, epieos |
| 1K to 10K | reverse username lookup, reverse username search, username lookup, username search free, social media username search, username availability checker, digital footprint checker, free osint tools, instagram osint, osint instagram, osint search engine, sherlock username search, sherlock osint, discord user id lookup, gamertag lookup, reddit user lookup, telegram username search, tiktok username search, data breach check, instant username |
| 100 to 1K | osint app, delete old accounts, find old accounts, epieos alternative |
| 10 to 100 | sherlock alternative, deactivate vs delete account, osint android, github user lookup |

**Misspellings.** I submitted typo spellings (osnit, osint tolls, usernmae search). As far as the export shows, they came back without rows of their own. Keyword Planner groups close variants, and GSC already shows typo queries landing on correct pages: "username search osnit" at 14.7, "sherlocq alternatives" at 9.3. Ranking for the correct term is how a site ranks for its misspellings.

## 3. Who ranks, and how

**"username search" and "reverse username lookup"** (US results, 28 Nov):

- instantusername.com
- revealer.us
- whatsmyname.io
- whatsmynameapp.us
- footprintiq.app
- predictasearch.com
- fingerprint.to
- intelbase.is
- handle.tools
- socialcatfish.com

What these pages share:

- One page per tool intent.
- The exact query sits at the front of the title. Example: "Username Lookup: Reverse Username Search Across 800+ Platforms".
- The H1 matches the query.
- The search box sits above the fold, followed by a sample result, short sections and an FAQ.
- Several are young domains that borrow a known name: WhatsMyName was archived on 9 Nov 2026.

**"discord id lookup":**

- discordlookup.org
- discorder.tools
- discord.id
- dc.gg
- vibebot.gg
- Discord support
- friendcordapp
- ticket-tool.app
- vaultcord

These are all small single-purpose tools. The leaders show the profile name and avatar, which they get through Discord's API with a bot account.

## 4. Plan

1. **Freeze titles and URLs on anything with impressions** until the December core update has finished and settled. The 11-27 edits went live on 28 Nov at the user's request; do not stack more retitles on top of them.
2. **Tool-first pages for real-volume queries where a working tool is what wins.**
   - **Done 28 Nov:** `/discord-id-lookup.html` (10K to 100K a month). It decodes in the browser and is linked from the sitewide footer.
   - **Phase 2:** show the name and avatar through Discord's `GET /users/{id}`. This needs a free Discord bot token from the user, set on Render. Discord allows 50 requests a second per bot. Cache the results.
   - **Next candidates** that already have a guide to build from: username availability checker (1K to 10K), gamertag lookup (1K to 10K), reddit user lookup (1K to 10K), telegram username search (1K to 10K), tiktok username search (1K to 10K). Each must be a working tool, not a templated page.
3. **Quality before the December update.** The 11-26 and 11-27 additions look trend-chasing: the "2026-2027" pages, upcoming-osint-tools-2027, the typo paragraphs and the glossary typo table. They should be re-judged on data at the 9 Dec check. On 28 Nov the user chose to keep the typo text, but also to ship the 11-27 tree, which had already removed most of it. What is still live: the glossary typo table (osint-glossary.html), guides/what-is-osint.html and one homepage line. The removed blocks are on discovery pages and listicles.
4. **Authority, the user's actions.** A two-month-old domain cannot hold page 1 for "username search" on on-page work alone. Actions:
   - AlternativeTo listing (as an alternative to Sherlock, WhatsMyName and Namechk).
   - Product Hunt launch.
   - Follow up on OSINT Framework PR #933.
   - Awesome-OSINT list PRs.
   - Genuine r/OSINT answers that link the Discord ID tool where it fits.
5. **Measure the right thing.** Average position falls every time a page starts appearing at position 70 for a broad term. Track instead:
   - clicks
   - the count of queries in the top 10
   - impressions per page for the tool pages

   Re-judge on 9 Dec (7 days against the previous 7), and again after the December update completes.
