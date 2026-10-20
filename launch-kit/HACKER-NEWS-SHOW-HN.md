# Hacker News Launch Guide: "Show HN"

Hacker News (`news.ycombinator.com`) is one of the highest-yield launch pads for technical tools. A front-page post can generate 15,000–40,000 technical visitors, hundreds of GitHub stars, and organic mentions across newsletters and podcasts.

---

## 1. Submission Details

- **Submission URL:** `https://news.ycombinator.com/submit`
- **Submission Type:** Link
- **URL to submit:** `https://www.myrecon.xyz` (or `https://github.com/4ryanwalia/Myrecon`)
- **Best Time to Post:** Tuesday or Wednesday between 06:30 AM – 08:30 AM EST (11:30 – 13:30 UTC).

---

## 2. Tested Title Options

Choose one of the following depending on whether you link to the web app or GitHub repo:

### Option A (Recommended — Technical & Direct):
> **Show HN: MyRecon – Open-source username OSINT with an evidence-aware verdict engine**

### Option B (Problem-focused):
> **Show HN: MyRecon – Username search without false positives from login walls**

### Option C (Data/API focused):
> **Show HN: MyRecon – Keyless public breach API and multi-platform username audit tool**

---

## 3. First Comment (Post Immediately After Submitting)

Post this comment from the submitter account within 60 seconds of posting the link:

```markdown
Hi HN! I built MyRecon (https://www.myrecon.xyz and https://github.com/4ryanwalia/Myrecon) to solve a problem that bugged me with existing username search tools: false positives.

Most username tools rely on HTTP 200 checks or naive string matching. When a platform responds with a login wall, Cloudflare challenge, rate limit, or custom 200 error page, tools like Sherlock or generic scrapers often label it as "Found". For researchers and people doing personal security audits, this creates false confidence and wasted time.

### How MyRecon works:
1. **Three-State Verdict Contract:** Every lookup returns `found`, `not_found`, or `unknown`. If a site hits a CAPTCHA, redirect, timeout, or login wall, it explicitly returns `unknown` rather than guessing.
2. **500+ Platforms:** Built with custom platform signatures, JSON streaming, and synthetic test suites.
3. **Open Architecture & Keyless Data API:** In addition to the CLI and web app, we publish daily breach metadata at `https://www.myrecon.xyz/data/v1/` as free, keyless, CORS-enabled static JSON (CC BY 4.0 via HIBP) so developers can embed breach feeds without needing API keys.
4. **Reproducible Benchmarks:** We run and publish daily automated comparison runs against Sherlock and Maigret on fixed handles so anyone can inspect raw verdict data.
5. **Interactive Tools:** We also added an interactive OSINT Cheat Sheet & Google Dork generator at https://www.myrecon.xyz/osint-cheat-sheet.html.

The backend is Python/Flask, and the frontend is static HTML/JS deployed on Vercel with streaming NDJSON scan progress.

The CLI and synthetic demo run completely offline with no API keys:
`git clone https://github.com/4ryanwalia/Myrecon.git && python examples/offline_demo.py`

I’d love feedback from the HN community on platform coverage, rate-limit resilience, and the verdict contract!
```

---

## 4. Response Playbook for Common HN Questions

### Q: "How does this compare to Sherlock or Maigret?"
> *Response:* "Sherlock is legendary and fast, and Maigret does deep profile parsing. Where MyRecon focuses is the verdict contract: we treat any inconclusive state (login wall, HTTP challenge, rate limit, ambiguous redirect) as `unknown` rather than reporting an account. We publish daily benchmark runs side-by-side with raw JSON at https://www.myrecon.xyz/#benchmarks so you can inspect the exact divergence."

### Q: "Is this legal/ethical?"
> *Response:* "MyRecon only accesses public web responses and public breach metadata. It does not bypass authentication, scrape behind private walls, or sell private data. It is primarily built for individuals auditing their own digital footprint and authorized security researchers."

### Q: "How do you avoid Cloudflare / Bot blocks?"
> *Response:* "By not lying about it. When a site blocks automated checks, MyRecon logs it as `unknown` with the error type instead of pretending it found a profile. For local investigations, our CLI allows setting local proxies, headers, and rate delays."
