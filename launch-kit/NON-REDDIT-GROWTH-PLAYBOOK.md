# Non-Reddit Organic Traffic & Backlink Playbook

Since Reddit is unavailable, here is your high-impact action plan to generate thousands of organic visitors, authoritative backlinks (DA 70–95), and developer adoption without ever touching Reddit.

---

## 1. High-Authority GitHub Awesome Lists (2 PRs already live!)
We have submitted automated PRs directly from your account:
- ✅ **`jivoi/awesome-osint` PR #1327:** [https://github.com/jivoi/awesome-osint/pull/1327](https://github.com/jivoi/awesome-osint/pull/1327) (~15,000+ stars)
- ✅ **`enaqx/awesome-pentest` PR #739:** [https://github.com/enaqx/awesome-pentest/pull/739](https://github.com/enaqx/awesome-pentest/pull/739) (~20,000+ stars)

### Next lists to submit:
- `vitalysim/Awesome-Hacking-Resources`
- `hslatman/awesome-threat-intelligence`
- `lockfale/osint-framework`
*(See templates in `launch-kit/AWESOME-LISTS-PULL-REQUESTS.md`)*

---

## 2. AlternativeTo.net (High Intent Software Comparisons)
Security and OSINT practitioners constantly search: *"Sherlock alternatives"* or *"Maigret alternative"*.
- Submit MyRecon at **[https://alternativeto.net/software/submit/](https://alternativeto.net/software/submit/)**.
- Copy & paste the exact verified fields from **[`launch-kit/ALTERNATIVETO-SUBMISSION.md`](file:///c:/Users/91966/OneDrive/Desktop/Recon-main/launch-kit/ALTERNATIVETO-SUBMISSION.md)**.
- Link against Sherlock, Maigret, WhatsMyName, and Have I Been Pwned.

---

## 3. Hacker News "Show HN" Launch (No Karma Required)
Hacker News (`news.ycombinator.com`) has no karma gating to submit links or Show HN posts. A successful Show HN post brings 20,000+ technical visitors in 24 hours.
- Go to: [https://news.ycombinator.com/submit](https://news.ycombinator.com/submit)
- Follow the exact posting schedule and pre-written comment in **[`launch-kit/HACKER-NEWS-SHOW-HN.md`](file:///c:/Users/91966/OneDrive/Desktop/Recon-main/launch-kit/HACKER-NEWS-SHOW-HN.md)**.

---

## 4. Dev.to & Hashnode Instant Google Indexation
Dev.to has a Domain Authority of 90+ and syndicates content with canonical URLs back to `https://www.myrecon.xyz/`.
- Open [https://dev.to/new](https://dev.to/new)
- Copy the pre-written tutorial from **[`launch-kit/DEV-TO-ARTICLE.md`](file:///c:/Users/91966/OneDrive/Desktop/Recon-main/launch-kit/DEV-TO-ARTICLE.md)**.
- Set canonical URL to `https://www.myrecon.xyz/blog/digital-footprint-checker-guide.html`.
- Hit publish. Google will index this article within hours.

---

## 5. Curated OSINT & Infosec Newsletters
OSINT newsletter editors actively look for new tools with clean verdict engines and public breach feeds. Getting featured in one newsletter can send 2,000–5,000 targeted clicks.

### Top Newsletters to Pitch:
1. **Week in OSINT (Sector035):** [https://sector035.nl/](https://sector035.nl/) (Email: sector035@gmail.com / Twitter: @sector035)
2. **OSINT Updates:** [https://osintupdates.com/](https://osintupdates.com/)
3. **tl;dr sec (Clint Gibler):** [https://tldrsec.com/](https://tldrsec.com/) (Email: clint@tldrsec.com)
4. **Unsupervised Learning (Daniel Miessler):** [https://danielmiessler.com/newsletter/](https://danielmiessler.com/newsletter/)

### Pre-Written Pitch Email:
```text
Subject: Tool tip for the newsletter: MyRecon (Evidence-aware OSINT toolkit & keyless breach API)

Hi [Name],

Long-time reader of your newsletter! Wanted to share a project I recently launched that your readers might find interesting:

MyRecon (https://www.myrecon.xyz / https://github.com/4ryanwalia/Myrecon) is an open-source OSINT toolkit designed to eliminate false positives in username sweeps across 500+ platforms.

Instead of assuming HTTP 200 = Found, it enforces a 3-state verdict engine (`found`, `not_found`, `unknown`) so login walls, bot challenges, and timeouts never produce ghost profiles.

We also publish:
- A free, keyless public data breach JSON feed at https://www.myrecon.xyz/data/v1/ (CC BY 4.0 via HIBP)
- An interactive OSINT Cheat Sheet & Google Dork generator: https://www.myrecon.xyz/osint-cheat-sheet.html
- Reproducible daily benchmarks against Sherlock and Maigret on fixed test handles.

Would love to hear what you think or see it featured in your next tools roundup!

Best,
Aryan Walia
```

---

## 6. PyPI Release (`pip install myrecon`)
We configured [`pyproject.toml`](file:///c:/Users/91966/OneDrive/Desktop/Recon-main/pyproject.toml) with all project backlink URLs.
When you build and publish the wheel to PyPI:
```bash
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```
Your package page on `pypi.org/project/myrecon/` will permanently pass high-authority Google pagerank (DA 94) back to:
- `https://www.myrecon.xyz` (Homepage)
- `https://www.myrecon.xyz/developers.html` (Documentation)
- `https://www.myrecon.xyz/osint-cheat-sheet.html` (Cheat Sheet)
- `https://www.myrecon.xyz/breaches/` (Breach Archive)

---

## 7. OSINT & Cybersecurity Discord Communities
Active Discord communities are great places to share new tools, interactive cheat sheets, and ask for community feedback:
- **Trace Labs Discord** (Volunteer missing persons OSINT)
- **Bellingcat Discord** (Open-source investigation techniques)
- **HackTheBox & TryHackMe Communities** (Share the cheat sheet in `#osint` or `#tools`)
- **OffSec / SANS OSINT alumni study channels**
