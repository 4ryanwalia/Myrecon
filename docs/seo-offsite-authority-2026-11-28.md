# Off-site authority actions, 28 Nov 2026

These are for you to post yourself. AI answers and Google's "best X" results cite lists, directories and community threads rather than vendor homepages: Reddit appeared on 12 of 15 SERPs in `docs/ai-citation-check-2026-11-18.md` and on most of the 19 checked on 28 Nov.

Every post must say you built MyRecon. None should claim a rank, "best" or "top" status. Read each community's self-promotion rules before posting.

Ranked by expected value: how often the target appears on our SERPs, how much authority the link carries, and how much effort it takes.

| # | Target | Why it matters | Point it at | Effort |
|---|---|---|---|---|
| 1 | GitHub PR lockfale/OSINT-Framework#933 (open, last updated 19 Nov) | osintframework.com ranks #3 for "osint tools" (US, 28 Nov) | / | Low: one comment |
| 2 | AlternativeTo, "WhatsMyName Web Alternatives" (alternativeto.net) | Ranks #2 and #9 for "whatsmyname alternative"; the AI Overview names AlternativeTo | /whatsmyname-alternatives.html | Low |
| 3 | r/OSINT thread "Is Whatsmyname broken for anyone else?" | Ranks on page one for "is whatsmyname still maintained" | /whatsmyname-alternatives.html#how-many-whatsmyname-checks-still-work | Low |
| 4 | r/OSINT thread "Username-checking apps that don't completely suck?" | Ranks #1 for "whatsmyname alternative" | /username-checker.html#daily-benchmark | Low |
| 5 | GitHub soxoj/osint-namecheckers-list | Ranked for "sherlock alternative without python" on 18 Nov | / | Low: PR |
| 6 | GitHub jivoi/awesome-osint, Username Check section | The most-starred OSINT list; LLMs read it | / | Low: PR |
| 7 | OSINT Tools Library (tools.osintnewsletter.com), submission | Ranks #2 for "osint tools" and on page one for "is whatsmyname still maintained" | /whatsmyname-alternatives.html | Low: form |
| 8 | Bellingcat Online Investigations Toolkit, tool suggestion | Cited by journalists and AI answers on verification | /username-checker.html | Medium: needs a usable entry |
| 9 | Product Hunt launch of the Discord ID lookup | Gives the 28 Nov tool a dated launch and a backlink | /discord-id-lookup.html | Medium |
| 10 | Dev.to article (**outline only**: Dev.to's rules forbid AI-drafted posts) | Developer audience for the replay data | /downloads/whatsmyname-rule-replay-2026-11-27.csv | You write it |

## Drafts

Edit these into your own voice before posting. Numbers come from pages live on myrecon.xyz once this release ships.

### 1. OSINT Framework PR #933 follow-up comment

> Small update since I opened this: MyRecon now publishes a daily public-controls benchmark (10 fixed usernames on GitHub, GitLab and Hacker News, raw JSON at /data/benchmarks.json) so the entry can be checked against data rather than my description. Happy to change the category or wording if it fits better elsewhere. Disclosure: I build MyRecon.

### 2. AlternativeTo listing (add MyRecon as an alternative to WhatsMyName Web)

> MyRecon is a browser username search that checks 100 sites without an account and 560+ when signed in. It reports "unknown" separately from "not found" instead of counting blocked checks as misses. It also has an email breach lookup. The free tier has daily limits. Built by Aryan Walia.

Tags to choose: username search, OSINT, privacy. Do not tick "better than" comparisons.

### 3. Reply in "Is Whatsmyname broken for anyone else?"

> The project was archived on 9 Nov 2026, so its site rules are frozen. I replayed all 690 active rules on 27 Nov, each against the entry's own "known" account and a made-up handle. 291 (42%) still told them apart. 160 hit a 403 or 429 refusal, and 126 got a response neither rule expects. No made-up handle came back as "found". Method and per-site CSV: https://www.myrecon.xyz/whatsmyname-alternatives.html#how-many-whatsmyname-checks-still-work (I build MyRecon, one of the alternatives on that page.)

### 4. Reply in "Username-checking apps that don't completely suck?"

> The thing that makes most of them "suck" is counting any HTTP 200 as a hit. If you want to compare tools, look for ones that publish how often they're wrong. Disclosure: I build MyRecon. It runs a daily check of 5 real and 5 made-up usernames against the official GitHub, GitLab and HN APIs and publishes the raw results (https://www.myrecon.xyz/data/benchmarks.json). That's 3 platforms, not proof for the other 560, but you can see the method. Sherlock and Maigret are both in that same daily run.

### 5. soxoj/osint-namecheckers-list PR

Title: `Add MyRecon (web, free tier)`. Body:

> MyRecon: browser-based username search (100 sites as a guest, 560+ signed in), with unknown results kept separate from not-found. Free with daily limits; paid tier exists. Disclosure: I'm the developer.

Match the list's existing row format exactly.

### 6. jivoi/awesome-osint PR (Username Check section)

One line, matching the list's style:

> * [MyRecon](https://www.myrecon.xyz/) - Browser username search across 560+ sites that reports unknown results separately; free tier with daily limits.

### 7. OSINT Tools Library submission

Category: Username. Description: the same as #2, plus "Publishes a measured replay of the archived WhatsMyName rules (27 Nov 2026)."

### 8. Bellingcat Toolkit suggestion

Their entries follow a fixed template: URL, description, cost, requirements, limitations, ethical considerations, guides. Fill in Limitations honestly:
- signed-in scans have daily limits
- Instagram and other login-walled sites return "not confirmed"
- a username match is not identity

### 9. Product Hunt (Discord ID lookup)

Tagline (60 characters max): `Decode any Discord ID: creation date, avatar, mentions`

First comment:

> Discord IDs carry their own creation time. This decodes user, server, message and channel IDs in your browser and shows the public profile Discord returns for a user ID. No login. I built it as part of MyRecon.

### 10. Dev.to: outline only (write it yourself)

- Title idea: "I replayed WhatsMyName's frozen rules 18 days after it was archived"
- Why the archive matters to tools built on wmn-data.json (Blackbird and others)
- Method: own known handle, random control, own e/m rules, no redirects, one pass, one connection
- The table: 291 / 79 / 126 / 15 / 160 / 19
- The surprising part: zero false positives. Decay shows up as "can't decide", not as fake accounts
- Instagram example: a signed-out request now gets the same page for a real and a made-up account
- Caveats: one network, one day, 403s may pass elsewhere
- Link to the CSV (CC BY-SA 4.0, attribution to Micah Hoffman)

## Not proposed

- **Paid listings, link buys, guest posts:** against the no-paid rule and Google's link-spam policy.
- **Wikipedia:** no independent coverage exists to cite, so an entry would be removed.
- **Fake reviews, upvote rings, "top 10" self-claims:** refused.
- **Hacker News "Show HN":** worth doing only with the Dev.to write-up ready. Post it yourself, once, without asking anyone to vote.
