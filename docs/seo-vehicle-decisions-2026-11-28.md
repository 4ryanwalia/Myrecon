# Pillar 1: keyword vehicle decisions, 28 Nov 2026

Status: **proposal, waiting for approval.** Nothing in this table has been built.

## Method

- **GSC signal:** 28-day impressions and position (29 Oct to 25 Nov) from `docs/seo-baseline-2026-11-28.md`. Each page's own query table was used, not the page average.
- **Volume:** Keyword Planner ranges come from `docs/seo-recovery-plan-2026-11-28.md` (all locations, read 28 Nov). They appear as "KP" for context only.
- **SERPs:** each query was Googled on 28 Nov 2026 in the in-app browser with `gl=us&hl=en`, plus `gl=in` where India is relevant.
  - One navigate per query, read 6 seconds after load, so the AI Overview had time to render.
  - "Top-10 format" summarises the organic hostnames in order. "MyRecon" means a link to myrecon.xyz appeared anywhere on page one.
  - **MyRecon was linked on none of the 18 SERPs checked for it.** 19 were run, and the first ("username search") had no link check. That includes queries its pages held at 5 to 11 before the core update.
  - The browser was signed in to Google and ran from the user's own connection. `gl=us` sets the result country but not the searcher's real location, so read the US results as approximate.

## What the SERPs and the baseline say before any table

1. **The site is in a sitewide core-update demotion, not an indexing or format problem.**
   - Pages that matched their SERP format and held positions 5 to 11 (sherlock vs maigret, deactivate vs delete, osint app for android) are gone from page one.
   - Google's core updates page (developers.google.com/search/docs/appearance/core-updates, checked 28 Nov 2026) gives four pieces of advice:
     - Assess the site "as a whole".
     - "Evaluate the pages that were most impacted".
     - "Avoid doing 'quick fix' changes".
     - Expect that it "could take several months", possibly "until the next core update".
   - A December 2026 core update is preannounced. More URLs or format churn is the "quick fix" that page warns against.
2. **So the plan is upgrades, body only, on the pages that already earned real-intent positions.**
   - Titles, H1s and URLs stay frozen until 9 Dec under constraint 5.
   - **No new pages are proposed.** Every candidate query family already has a URL. Where the SERP wants a tool and we have only a guide, the proposal is to put a working tool on the existing URL, not to make a new one.
3. **One fresh fact has gone stale.** "Is whatsmyname still maintained" now gets an AI Overview that states the 9 Nov archival, citing LinkedIn and kitploit. MyRecon was #4 on that SERP on 18 Nov and is now absent.
   - The archival is no longer information gain on its own.
   - The AI Overview for "whatsmyname alternative" still does not mention the archival, so that query keeps the gap.

## Decision table

| # | Query family | Monthly signal (GSC impr / SERP evidence) | Top-10 format | AI Overview answers it? | Vehicle | Canonical URL | Existing / upgrade / new | Unique asset the page will hold | Country scope |
|---|---|---|---|---|---|---|---|---|---|
| 1 | osint app for android / osint apps android / osint tools for android | GSC 24 impr at 5.7 to 7.0 across 3 phrasings (26 at 26.0 for "tools"). KP "osint app" 100 to 1K | **Mixed:** 3 Play Store listings, reddit, GitHub, 1 listicle (techjockey), osint.industries, sourceforge | Partly. It lists WatchR (GitHub) and OSINT-D. It has no comparison of permissions or data collection | Disclosed ranked listicle (our existing format), plus the Play listing itself (ASO, your side) | /blog/best-osint-apps-for-android.html | **Upgrade** (body only) | **Each listed app's Play "Data safety" and permissions, read from its own Play page with a check date.** No top-10 result compares what these apps collect. MyRecon's own row gets the same treatment: its Data safety is read from the live Play page on the same day and quoted as is. Analytics have been on by default outside EEA/UK/CH since 1.20. Keeps "MyRecon publishes this list" and a "where X beats MyRecon" line for each app | Global |
| 2 | deactivate vs delete account (8 phrasings) | GSC about 15 impr at 8 to 11 for the question phrasings. KP 10 to 100 | Forums (reddit, quora), platform help (Facebook x2, Atlassian), saferinternet.org.uk, screenrant | **Yes, fully** for the generic question. PAA asks platform-specific versions (Instagram, "what friends see", "deactivated for 2 years") | How-to/explainer with a platform table (already the format) | /blog/account-deletion-vs-deactivation.html | **Upgrade** (body only) | **A per-platform table of deactivation limit, deletion grace period and what others see, each cell quoted from that platform's help page and dated.** The AI Overview gives only the generic answer. Answer the 4 PAA questions in 70 words or fewer. Fix 1 slow answer | Global |
| 3 | sherlock vs maigret / maigret vs sherlock | GSC about 13 impr at 4.8 to 11 across 5 phrasings. KP: maigret 10K to 100K, sherlock osint 1K to 10K | Comparison articles (footprintiq, osintverse, maxintel), reddit, linkedin, police1, quora, plus Facebook and Holmes noise | Partly. It splits between the OSINT tools and the fictional detectives | Head-to-head comparison (already the format) | /blog/sherlock-vs-maigret-vs-myrecon.html | **Upgrade** (body only) | **The 1 Nov 2026 35-control study, run against Sherlock and Maigret themselves.** Only this page holds that head-to-head. Competitors restate READMEs. It links to the daily benchmark on #10 instead of repeating it. Add "Where Sherlock beats MyRecon" and "Where Maigret beats MyRecon" sections. Fix 1 slow answer | Global |
| 4 | instagram osint / osint instagram / osint instagram private account | GSC 22 at 20.6, 9 at 26, 14 at 30.4 (same page). KP instagram osint 1K to 10K | Tools (osint.ly, hackdb Osintgram), GitHub Osintgram, guides (authentic8, aware-online), Instagram reels, reddit, youtube | Defines the term only. PAA: "How to search Instagram OSINT?", "Can we trace an Instagram ID?", "Is social media OSINT?" | Guide (the tool slots belong to Instagram-specific scrapers we will not build) | /blog/instagram-osint-public-profile-guide.html | **Upgrade** (body only) | **Our measured fact that Instagram blocks signed-out server-side checks**: the sweep engine reports Instagram as "not confirmed", pinned on 21 Nov. Re-measure and date it. Also Instagram's own Help Center wording on private accounts and data downloads, quoted and dated. **No "view private account" content**, and the guide states that this is not possible | Global |
| 5 | github user search / how to search github profiles / github username lookup | GSC 107 impr at 9.0 (page), "how to search github profiles" 2 at 9.5. KP github user lookup 10 to 100 | **Tools:** simonsmith github-user-search, braingainsoft, devpost, simonwillison lookup, GitHub's own search, GitHub Docs | Partly. It points to GitHub search qualifiers or "third-party API lookup tools" | **Tool page** (the SERP is tools) | /find/github-profile | **Upgrade:** add an in-browser lookup on the existing URL | **A working lookup that calls GitHub's public REST `GET /users/{username}` from the visitor's browser and shows `created_at`, public repos and followers.** GitHub Docs (checked 28 Nov 2026) document `GET /users/{username}` as public data with `created_at` in the schema. They state "The primary rate limit for unauthenticated requests is 60 requests per hour", applied per IP. Every call comes from the visitor's own IP, and nothing reaches our server. Whether github.com profiles show a join date was not checked, so the page makes no claim about it | Global |
| 6 | whatsmyname alternative / sites like whatsmyname | GSC 5 at 65.2, plus whatsmyname app alternative 4 at 76.8. KP whatsmyname 10K to 100K | Lists and directories: reddit, alternativeto x2, similarweb, aiagentsdirectory, osintcombine, shadowdragon, whatsmynameapp.us | Lists alternatives, but **does not say the project was archived on 9 Nov** (checked 28 Nov) | Comparison and alternatives page (already the format) | /whatsmyname-alternatives.html | **Upgrade** (body only) | **A dated measurement of the frozen 691-site dataset:** how many of its checks still give the right answer for a known-existing and a known-missing handle, run through our sweep engine on a stated date. Nobody else can publish "the frozen list is decaying at N%". If the measurement cannot be run honestly, the page gets no claim and only the existing archival facts stay | Global |
| 7 | how much do osint tools cost / osint pricing | Page: 37 impr at 6.3, 19 AI-feature impressions | Vendor pricing pages (osint.industries, forensicosint, osint-ui, osintverse, intelmind, maltego), listicles (shadowdragon, espectrosint), reddit | Gives ranges only ("free to thousands a year") | Cross-vendor dated price table (already the format) | /osint-tool-pricing.html | **Upgrade:** the monthly re-check due 15 Dec | **Every price re-read from the vendor page and re-dated.** MyRecon's own row loses the Black Friday wording once the sale ends. Add the vendors now on the SERP that the table lacks (osint-ui, osintverse, intelmind, OSINT Search Engine), each only if its price page is readable | Global |
| 8 | best data breach checker / breach alert app / "which services alert me…" | Page: 81 impr at 14.2, 35 AI-feature impressions (the second-highest page), ranking 1 to 10 for long AI-style questions | Tools: HIBP, databreach.com, Norton, F-Secure, Mozilla Monitor, Trend Micro, LeakPeek, proxynova, Quick Heal (gl=in) | Yes for "data breach check": it names HIBP. Not for "which services alert / monitor" | Disclosed listicle for the "best / which service" questions. The single check is HIBP's query and we do not chase it | /blog/best-data-breach-checkers.html | **Upgrade** (body only) | **Each service's alert mechanics (free or paid, what triggers an alert, which breach source it reads) quoted from its own help page and dated.** The 61-day breach-to-index median already lives in the India guide, so this page links to it instead of repeating it. Answer the exact AI-style questions as H2s | Global, with Quick Heal / gl=in noted |
| 9 | reverse email lookup / email osint | Page is **Crawled, currently not indexed** (crawled 25 Nov). KP: reverse email lookup and email osint each 10K to 100K | Tools: mailmeteor, emailosint.org, epieos, 1lookup, emailsherlock, behindtheemail, peoplesmart, plus 1 listicle (emailchaser) and reddit | Recommends EmailOSINT by name | **Tool page** (it already is one) | /reverse-email-lookup.html | **Upgrade:** content work so Google will index it | Google read the page and declined it, so the page needs something the others lack: **a dated, per-service table of what the breach and public-profile checks actually return, measured on a test address we own**, and an honest "what this does not do" section. The optional Holehe check (off by default) sends the address to each service it tests. The page already says so, checked in the built HTML on 28 Nov, and that wording must stay. Find the declined-index cause first (overlap with the email tab on / ?) | Global |
| 10 | username search / username checker (head) | GSC: username search 13 at 79, check username 8 at 77.8, free username checker 4 at 17.5. KP 10K to 100K | **Tools:** instantusername, revealer, whatsmyname.io, whatsmynameapp.us, intelbase, handle.tools, fingerprint.to, predicta, idsnoop | Lists tools by name (not us) | Tool page | / for "username search", /username-checker.html for "username checker" (documented split; homepage frozen) | **Upgrade** /username-checker.html only (body) | **The daily public-controls benchmark from `data/benchmarks.json`, held on this page only.** It runs 10 fixed handles (5 real, 5 made up) on GitHub, GitLab and Hacker News each day. It is worded as exactly that, never as accuracy across the 560+ catalogue. None of the 9 results' titles or snippets mention a published accuracy measurement. Their pages were not each opened, so the doc claims no more than that. The homepage stays untouched (it earns most clicks and is hand-edited) | Global |
| 11 | reverse username lookup / search | GSC: reverse username search 24 at 47, username reverse lookup 16 at 41, reverse username lookup 16 at 45. KP 1K to 10K | **Tools:** revealer, whatsmyname.io, socialcatfish, footprintiq, instantusername, whatsmynameapp.us, predicta, fingerprint.to, reddit | Defines the term only | Tool page (it already is one) | /reverse-username-lookup.html | **Upgrade** (body only) | **A sample result rendered from a real, dated run** (octocat), so the page shows output above the fold the way the leaders do. It links to the benchmark on #10 instead of repeating it (repeating it would add shared phrases between two near-twin tool pages). Name MyRecon in the first paragraph (the 15 Nov audit gap) | Global |
| 12 | find / delete old accounts | GSC: delete old accounts 8 at 65, how to delete old accounts 7 at 73.9, how to find old accounts 4 at 63 (split across 2 pages) | Guides: Consumer Reports Security Planner, reddit, Google support, perishablepress, Microsoft Q&A, NYT Wirecutter, Bitdefender | Yes, a step list | Guide | /blog/delete-old-online-accounts.html (rewritten 25 Nov, about 2,600 words) | **Existing, no body work now.** Merge blog/find-your-own-old-accounts.html into it **after 9 Dec**, with GSC query data attached | Already holds Google and Apple linked-app paths from their help pages. The merge removes the cannibalisation (title overlap 0.67, both on "old accounts") | Global |

### Looked at and not proposed

| Query family | Evidence | Why not |
|---|---|---|
| osint tools / best osint tools / free osint tools | GSC: osint tools 35 at 79.5, best osint tools 15 at 37.8. KP 10K to 100K | SERP: recordedfuture, osintframework, shadowdragon, osintcombine, osint.industries, GitHub topics, reddit. Directories and big-brand lists. The AI Overview answers it. Positions near 80 mean authority, not content. Canonical stays blog/best-free-osint-tools-for-investigators. The cannibal /free-osint-tool.html (159 impressions at 67.6) is a post-9-Dec decision |
| username availability checker | KP 1K to 10K, GSC 1 impression | SERP: pure availability tools (instantusername, namecheckup, handle.tools, dnschecker). Our engine's NOT_FOUND does not mean "available": reserved, banned and deleted names exist. An availability claim would be dishonest without per-platform proof |
| telegram username search | KP 1K to 10K, guide exists | SERP: tools (osint.ly, telegram-finder, footprintiq, metricgram). We cannot build an honest existence check, because t.me returns a page for any name (`echoes_handle`). The guide stays as is |
| discord id lookup | KP 10K to 100K | Built and shipped 28 Nov (/discord-id-lookup.html, with profile API). Indexing requested 28 Nov. Nothing more until it is indexed |
| free data breach api | GSC: breach api free 12 at 91.9, breach data api 10 at 90.8 | SERP: XposedOrNot, HIBP, LeakCheck, Hudson Rock, DeHashed, Enzoic. The intent is email-lookup APIs, and ours serves breach metadata only. developers.html already carries the sourced comparison. The open "Powered by LeakCheck" attribution from 25 Nov must be fixed first |
| data breach india 2026 (gl=in) | India 419 impressions in 28 days, mostly brand and long-tail | SERP: IBM report, news and monthly timelines (63sats, bitscore "33 data breaches", trinetra), Wikipedia. guides/india-data-breaches.html already exists (CERT-In 6-hour rule, local case files) and was requested 25 Nov. Give it time before adding work |
| Other countries (UK, Brazil, Canada, Indonesia) | 290, 150, 117 and 103 impressions, no country-specific queries in GSC | No local laws, regulators or breaches gathered. They get no pages (constraint 4) |
| sherlock.xyz alternatives | 160 impressions at 7.9, 0 clicks | A different product (the Web3 audit firm). Not our intent |
| gamertag lookup, reddit user lookup | KP 1K to 10K each | SERPs not checked this pass, to save Google request budget. Guides exist and were just requested for indexing. Revisit at the 4-week check |

## Count

- 11 upgrades (#1 to #11) and 1 post-freeze merge (#12).
- **0 new pages.** No query family lacks a URL, and the site is in a core-update demotion where more URLs is the wrong lever.
- #5 and #9 put tools on existing URLs, because their SERPs are tool-format.

## Build order if approved

The brief's priority is the 6 to 21 band first:

1. #1, #2, #3: real-intent queries that ranked 5 to 11 before the update.
2. #4, #8, #7: still 6 to 21, and they earn AI-feature impressions.
3. #5: a tool on a page that was at 9.0.
4. #6: depends on the measurement being runnable.
5. #10, #11: head terms, an authority problem; upgrades help eligibility only.
6. #9: diagnose why Google declined it first.
7. #12: after 9 Dec.

## Rules for every upgrade

- The title, H1, URL and meta description stay byte-identical until 9 Dec. Only the body changes.
- Every external fact is read from its primary source and carries "checked DD Mon 2026". A source that will not load produces no claim.
- Each H2 is a real GSC or PAA question, answered in 70 words or fewer.
- Listicles keep their disclosure and add "where X beats MyRecon".
- No em dashes. Counts are floors (560+, 3,000+).
- No Review or AggregateRating schema. No stalking framing. No hidden text.
- `npm run test:seo` and the 75% overlap test must pass. Build with `TZ=UTC node scripts/build-site.js` and commit only intended files.

## Your decisions needed

1. Approve, trim or reorder #1 to #11.
2. **Timing.** Body upgrades shipped before 9 Dec mix into the 7-vs-7 re-judge, so that comparison can no longer separate their effect from the update's. Ship #1 to #3 now and record ship dates in the re-measure plan, or start Phase 2 after the 9 Dec read?
3. #6: may I run the WhatsMyName frozen-dataset measurement through the sweep engine (backend), or keep that page to text changes? The dataset is CC BY-SA 4.0, so a published measurement derived from it needs attribution and the same licence on the derived numbers. Before running anything I would check whether each WhatsMyName entry already lists a known-existing handle, which would remove the need for invented controls.
4. #5: OK to add a client-side GitHub API call on /find/github-profile? It changes the page's CSP `connect-src` to allow api.github.com.
5. Confirm that the three freeze-list items in the baseline (the Instagram retitle and the two redirects) wait for 9 Dec.
