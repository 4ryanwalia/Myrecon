# AI answer citation check, 18 November 2026

Method: Google search in the Claude desktop browser pane, `hl=en&gl=us`, logged
out, page text read about 4 seconds after load. "Not cited" means myrecon.xyz did
not appear in the AI Overview sources or the part of the results page that was
read (roughly the top 6 to 10 organic results). This is one observation from one
location, not a rank tracker. Repeat monthly with the same queries.

Not checked: ChatGPT (needs sign-in) and Perplexity (a logged-out query returned
"Sign up and repeat your request"). Both need a signed-in check by the owner.

| # | Query | AI Overview shown | MyRecon cited / ranked | Who is cited instead | What they have that we lack |
|---|---|---|---|---|---|
| 1 | whatsmyname alternative | Yes | No | whatsmynameapp.us, AlternativeTo, X post by OSINTtechniques; r/OSINT thread ranks first | Crowd lists (AlternativeTo), a Reddit thread. The overview does not mention the 9 Nov archive at all |
| 2 | is whatsmyname still maintained | No (still loading when read) | Yes, organic, about 4th (/whatsmyname-alternatives) | LinkedIn post, intelmind.io, kitploit | Already competitive. LinkedIn post is from a known OSINT practitioner |
| 3 | sherlock username search alternative without python | No | No | osint-ui.com (two posts), whatsmynameapp.us, soxoj/osint-namecheckers-list (GitHub), Medium comparison | A GitHub list entry (soxoj list), a hands-on Medium comparison |
| 4 | why do username checkers show false positives | Yes | No | spiderfoot.tools (all five overview points), r/OSINT | We have original measured data (control study) that the cited page lacks, but the page is not ranking for this wording |
| 5 | what does it mean if my email is not found in a data breach check | No | No | secria.me, HIBP FAQ, traceerase.co.uk, Reddit | Our /blog/breach-check-no-results-meaning.html matches this intent but was not in the results read |
| 6 | how much do osint tools cost | No | No | OSINT Industries pricing, ShadowDragon, intelmind, Forensic OSINT, Espectrosint, Comparitech | Vendor pages and listicles. Our dated 14-tool price guide (15 Nov) is new and may not be indexed for this yet |
| 7 | sherlock vs maigret | No | No | footprintiq.app, osintverse.com, r/OSINT, Police1 | Short verdict line at the top ("Maigret finds more, Sherlock is quicker") |
| 8 | free data breach api | No | No | XposedOrNot, HIBP API, LeakCheck, Hudson Rock | Intent is email lookup; our API is breach metadata only and cannot query an email, so this is not our query |
| 9 | best free username search tool | Yes | No | whatsmynameapp.us and whatsmyname.io (both unaffiliated with the archived project), Instant Username Search, ShadowDragon | Overview leads with a site claiming "732 platforms" |
| 10 | how to find my old social media accounts | Yes | No | Avast blog, GitHub, Social Searcher, Consumer Reports, YouTube | Step lists starting with inbox search, which our page also has |
| 11 | have i been pwned breach date vs added date | Yes | No | HIBP, ProstDev, Wikipedia, UserVoice | Our /blog/breach-date-vs-disclosure-date.html covers this; not in results read |
| 12 | free digital footprint checker | Yes | No | whatsmynameapp.us, FootprintIQ, Malwarebytes, Bitdefender, Aura, Incogni | Big security brands with free scans |
| 13 | is myrecon legit | Yes | Play listing only; /is-myrecon-legit.html not cited | ScamAdviser (for unrelated myrecon.shop), Google Play | Overview mixes us with an unrelated store. Fixed the page opening in commit 9e4e25d2 |
| 14 | castlerat data breach | Yes | No | Europol, Shadowserver Foundation, OptMsg, LinkedIn | Law-enforcement and Shadowserver primary sources |
| 15 | how to check if my email was in a data breach | Yes | No | HIBP, Secria, ProstDev, Mozilla Monitor, Reddit | Brand authority |

## What this says

- Where we rank, it is on a dated fact others lack (query 2). That pattern is the one to repeat.
- Lists and threads are cited (AlternativeTo, soxoj/osint-namecheckers-list, r/OSINT). Getting listed there is off-site work for the owner.
- Unaffiliated WhatsMyName-branded sites are winning the AI Overview for generic username queries (1, 9, 12).
- Queries 5 and 11 have a matching MyRecon page that does not show. Search Console data is needed to see whether those pages get impressions at all before rewriting them.
