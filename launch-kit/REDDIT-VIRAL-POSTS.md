# Reddit Community Launch & Viral Post Templates

Reddit can generate tens of thousands of organic visits and high-intent backlinks from forums, but posts must prioritize educational value, technical transparency, and genuine discussion rather than blatant self-promotion.

---

## 1. Subreddit: r/OSINT (Subscribers: 120,000+)

### Title:
`Why username OSINT tools give false positives on login walls (and how we built an evidence-based verdict engine)`

### Post Body:
```markdown
Hey everyone in r/OSINT,

If you’ve ever run a username tool like Sherlock, WhatsMyName, or Maigret, you’ve probably noticed that a decent percentage of "Found" accounts are false positives:
- The site responded with an HTTP 200 containing a sign-in or paywall.
- The platform redirected to a generic "user not found" page with a 200 OK status code.
- Cloudflare threw a 403 or challenge page, and the scraper couldn't distinguish it from an existing user.

I've been working on an open-source OSINT toolkit called **MyRecon** (https://www.myrecon.xyz / https://github.com/4ryanwalia/Myrecon) to address this exact limitation.

### How we handle verdicts:
Instead of a binary Yes/No:
1. **Found:** Only returned when positive profile markers (DOM element, user JSON, or differential response against a known missing-user control) are matched.
2. **Not Found:** Verified against negative evidence or 404/410 codes.
3. **Unknown:** Whenever there’s a timeout, CAPTCHA, login wall, or bot block, it is explicitly reported as `unknown`. An inconclusive lookup remains inconclusive.

### What’s available:
- **Web App:** Fast multi-platform scanner with live NDJSON streaming (https://www.myrecon.xyz)
- **Interactive OSINT Cheat Sheet:** We built a live Google Dork / query generator for username, cloud storage, and breach queries: https://www.myrecon.xyz/osint-cheat-sheet.html
- **Public Data API:** Keyless, CORS-enabled daily breach metadata feed (CC BY 4.0 via HIBP) at `https://www.myrecon.xyz/data/v1/`
- **CLI & Offline Demo:** You can clone and run synthetic tests completely offline without network requests:
  `python examples/offline_demo.py`

Would love to hear how other investigators here handle login walls and rate limiting in your automated workflows!
```

---

## 2. Subreddit: r/privacy (Subscribers: 1,500,000+)

### Title:
`How to do a complete self-audit of your online footprint and forgotten usernames (Step-by-step checklist)`

### Post Body:
```markdown
Most people have accounts on 100+ websites that they opened years ago and completely forgot about. These abandoned accounts are often the exact vectors exploited in credential-stuffing attacks and data breaches.

Here is a practical checklist for auditing your own footprint:

1. **Inventory your old usernames & handles:**
   List all variations of handles you used in school, gaming, and early forums.
2. **Scan across platforms with evidence verification:**
   Use an open-source username search tool (like Sherlock or our tool MyRecon: https://www.myrecon.xyz) to check where your handle is currently registered.
3. **Check breach exposure without leaking passwords:**
   Look up whether your email or old usernames appeared in known breaches. We host a searchable breach catalog and keyless public feed at https://www.myrecon.xyz/breaches/
4. **Search pastebins and public indices:**
   Use Google dorks to check for public paste dumps or exposed lists. We put together an interactive query generator here: https://www.myrecon.xyz/osint-cheat-sheet.html
5. **Delete & purge old profiles:**
   Follow deletion workflows rather than just deactivating. (Check our guides on data broker opt-outs: https://www.myrecon.xyz/privacy/).

What other methods or tools do you use to clean up legacy accounts?
```

---

## 3. Subreddit: r/Python (Subscribers: 1,200,000+)

### Title:
`I built an open-source OSINT toolkit in Python with an offline verdict engine and async streaming`

### Post Body:
```markdown
Hi r/Python!

I wanted to share **MyRecon** (https://github.com/4ryanwalia/Myrecon), a Python-powered OSINT and footprint investigation tool.

### Technical Highlights:
- **Architecture:** Shared core services between a Flask API and a rich terminal CLI (`cli/__main__.py`).
- **Offline Synthetic Test Harness:** The test demo (`examples/offline_demo.py`) demonstrates our 3-state verdict engine (`found`, `not_found`, `unknown`) without touching external network endpoints or needing API keys.
- **Async & Streaming:** Streams scan progress over NDJSON (Newline Delimited JSON) to the web UI (https://www.myrecon.xyz).
- **Public Static Data API:** Emits daily versioned JSON feeds under `/data/v1/` with zero database overhead.

Check out the code on GitHub: https://github.com/4ryanwalia/Myrecon
Feedback and PRs on our check modules are very welcome!
```

---

## 4. Subreddit: r/netsecstudents & r/cybersecurity

### Post Title:
`Free OSINT Cheat Sheet & Google Dork Generator for Footprint Auditing`

### Body Summary:
Focus on the practical utility of `https://www.myrecon.xyz/osint-cheat-sheet.html` for CTF challenges, footprint analysis, and student lab exercises.
