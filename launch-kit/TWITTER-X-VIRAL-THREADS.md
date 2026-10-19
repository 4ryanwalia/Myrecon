# Twitter / X Viral Thread Templates

Twitter/X is a major hub for the cybersecurity, #OSINT, and infosec communities. These threads are structured for high bookmarks, retweets, and organic backlink citations.

---

## Thread 1: "The 3-Minute Digital Footprint Audit" (High Virality & Bookmarks)

**Tweet 1 (Hook):**
Most people have 100+ abandoned accounts on the web that they created years ago and forgot about.

These accounts are goldmines for credential stuffing and identity correlation.

Here is how to audit your entire digital footprint in 3 minutes (free & private) 🧵👇

**Tweet 2:**
1️⃣ **Uncover your forgotten usernames across 500+ platforms**

Don't search manually. Use an evidence-based username scanner to discover where your old handles still exist:
👉 https://www.myrecon.xyz

It checks 500+ platforms and filters out false positives from login walls and timeouts.

**Tweet 3:**
2️⃣ **Check your credential breach exposure**

Has your primary or secondary email leaked in a corporate database dump?

Check whether your accounts appeared in stealer logs or public breaches without uploading sensitive data:
👉 https://www.myrecon.xyz/breaches/

**Tweet 4:**
3️⃣ **Scan pastebins and public indices using OSINT Dorks**

Search for exposed config files, combo lists, and public paste dumps referencing your handle or domain:

We built a free interactive Google Dork generator:
👉 https://www.myrecon.xyz/osint-cheat-sheet.html

Type your handle and get one-click search operators.

**Tweet 5:**
4️⃣ **Permanently delete inactive accounts**

Deactivating is not deleting. When you deactivate, data brokers and scrapers can still access historic records.

Follow step-by-step removal guides for major platforms:
👉 https://www.myrecon.xyz/privacy/

**Tweet 6 (CTA):**
All these tools are free and open-source:
🌐 Web App: https://www.myrecon.xyz
⭐ GitHub: https://github.com/4ryanwalia/Myrecon
📊 API: https://www.myrecon.xyz/developers.html

If you found this useful:
1. Retweet Tweet 1 to help friends clean their footprint.
2. Bookmark this thread for your next security check!

---

## Thread 2: "The Engineering Behind 0% False Positive Username Scans"

**Tweet 1 (Hook):**
Why do most username OSINT tools return fake accounts?

Because 90% of tools rely on a naive "HTTP 200 = Found" heuristic.

Here is why that breaks, and how we solved it in MyRecon 🧵👇

**Tweet 2:**
When a site hits:
- Cloudflare bot challenges
- A sign-in redirect
- A 200 OK custom error page
- A rate-limit throttle

Tools like Sherlock often report: "Found: target". That’s a false positive.

**Tweet 3:**
In MyRecon, we implemented a 3-State Verdict Contract:
✅ `found`: Only with positive DOM/API evidence
❌ `not_found`: Confirmed negative evidence
❓ `unknown`: Inconclusive state (login wall, CAPTCHA, timeout)

An inconclusive lookup stays inconclusive.

**Tweet 4:**
We even publish daily automated benchmark comparisons against Sherlock and Maigret on fixed test handles:
👉 https://www.myrecon.xyz/#benchmarks

Inspect the raw data and reproduce the tests yourself.

**Tweet 5:**
Try the offline demo without network calls:
`git clone https://github.com/4ryanwalia/Myrecon.git`
`python examples/offline_demo.py`

Web App: https://www.myrecon.xyz
Star the repo on GitHub: https://github.com/4ryanwalia/Myrecon
