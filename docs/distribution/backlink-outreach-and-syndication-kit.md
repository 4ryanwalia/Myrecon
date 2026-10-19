# MyRecon Web Presence & Backlink Syndication Kit

This kit provides ready-to-publish assets and outreach templates to build high-authority external backlinks, establish presence across developer and cybersecurity communities, and drive genuine organic traffic to **https://www.myrecon.xyz**.

---

## 1. Curated GitHub Directory PR Submissions

Submitting MyRecon to top open-source OSINT resource repositories is one of the fastest ways to gain high-authority dofollow backlinks from GitHub (Domain Authority: 96+).

### Target 1: [Awesome-OSINT (jivoi/awesome-osint)](https://github.com/jivoi/awesome-osint)
* **Section:** `Username Check / Social Media`
* **Entry to Add:**
```markdown
* [MyRecon](https://www.myrecon.xyz/) - Evidence-aware public username search across 500+ platforms with false-positive controls and email breach exposure checks.
```

### Target 2: [Awesome Privacy (pluja/awesome-privacy)](https://github.com/pluja/awesome-privacy)
* **Section:** `OSINT & Self-Auditing`
* **Entry to Add:**
```markdown
* [MyRecon](https://www.myrecon.xyz/) - Web tool for personal digital footprint audits, username enumeration, and data breach exposure checks.
```

---

## 2. Dev.to / Medium / Hashnode Canonical Cross-Posting

Publishing tutorials on developer networks with an explicit **canonical link** transfers search authority (PageRank) to your domain without any duplicate content penalty.

### Post Template: "How to Build a True Username OSINT Scanner (Without False Positives)"
* **Canonical URL:** `https://www.myrecon.xyz/blog/reverse-username-lookup-guide.html`
* **Tags:** `#cybersecurity #osint #python #infosec`
* **Summary Content:**
```markdown
---
title: Why Most Username OSINT Tools Give False Positives (And How to Fix It)
published: true
tags: cybersecurity, osint, privacy, python
canonical_url: https://www.myrecon.xyz/blog/reverse-username-lookup-guide.html
---

When investigating digital footprints, most beginner tools make a fatal mistake: they assume an HTTP 200 status code proves an account exists.

In reality, modern web applications employ single-page apps (SPAs), login walls, soft 404s, and aggressive anti-bot rate limits. Requesting a nonexistent handle often returns HTTP 200 with a "Register this name" landing page!

### The Control Handle Heuristic
To solve this, professional tools compare candidate requests against a control handle: an impossible string like `__myrecon_impossible_handle_992__`.

If the server responds identically to both the real handle and the impossible handle, the status code carries zero evidence.

We break down the entire methodology and full platform comparison in our deep dive on [MyRecon's Reverse Username Lookup Guide](https://www.myrecon.xyz/blog/reverse-username-lookup-guide.html).
```

---

## 3. Reddit Community Submissions

When posting to Reddit, lead with genuine educational value and technical methodology rather than promotion.

### Post for `r/OSINT` and `r/cybersecurity`
* **Title:** A practical breakdown of why HTTP 200 codes cause false positives in username enumeration (and how to corroborate findings)
* **Body:**
```markdown
Hey everyone,

Over the past few months building tools for digital footprint auditing, one of the biggest challenges I noticed with open-source handle scanners is how frequently they mistake a login wall, soft 404, or rate limit for an active account.

I wrote up a detailed methodology covering:
1. Why status codes alone are deceptive (SPAs and WAF redirects).
2. The synthetic control handle test (measuring whether an impossible string returns the same response).
3. The chain of corroboration required before attributing a handle to an individual (avatars, stylometry, bio links).

If anyone is conducting self-audits or due diligence research, you can read the full guide and explore our open benchmarks here:
https://www.myrecon.xyz/blog/reverse-username-lookup-guide.html

Would love feedback from other researchers on how you handle platform rate limits during large sweeps.
```

### Post for `r/privacy`
* **Title:** The 2026 Checklist to Audit and Delete Your Digital Footprint (Self-Defense Guide)
* **Body:**
```markdown
Most people have created between 50 and 150 online accounts over their lifetime, many of which remain dormant and vulnerable to credential stuffing leaks.

We put together a comprehensive step-by-step checklist on how to find forgotten accounts, remove personal data from Google Search ("Results about you"), and opt out of commercial data brokers:
https://www.myrecon.xyz/blog/how-to-remove-yourself-from-the-internet.html

Key steps covered:
- Using email search operators to find old activation emails.
- Manual opt-out links for Spokeo, BeenVerified, Whitepages, and Radaris.
- How to request PII removal directly from Google search indices.
```

---

## 4. Hacker News "Show HN" Draft

* **Title:** Show HN: MyRecon – Evidence-aware username and digital footprint audit tool
* **URL:** `https://www.myrecon.xyz`
* **Text / Comment:**
```text
Hi HN,

I built MyRecon (https://www.myrecon.xyz) to solve a common frustration with username enumeration tools: false positives caused by WAFs, single-page apps, and login walls returning HTTP 200 responses for nonexistent accounts.

MyRecon checks 500+ platforms by comparing responses against synthetic control handles, categorizing results strictly as 'found', 'not_found', or 'unknown' (when uncertainty prevents a conclusion).

We also provide a free, keyless data breach metadata API (https://www.myrecon.xyz/developers.html) with CORS enabled, rebuilt daily.

The code and Python CLI are open source on GitHub: https://github.com/4ryanwalia/Myrecon

I would love your feedback on the methodology and user experience.
```
