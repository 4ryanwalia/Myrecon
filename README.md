# MyRecon — OSINT Intelligence Platform

**myrecon.xyz** — a fast, accurate, privacy-respecting open-source intelligence
platform. Search usernames across 100+ platforms, analyze emails and breach
exposure, and investigate domains, DNS, and IP addresses from reliable public
data sources.

The project is a **monorepo** split to match its deployment targets:

```
backend/    Flask REST API      → deploy to Render
frontend/   Static site (SPA)   → deploy to Vercel
```

The frontend never talks to third-party OSINT sources directly — it calls the
MyRecon API, which owns all validation, rate limiting, caching, and secrets.

---

## Architecture

| Concern              | Where                        | Notes                                                   |
| -------------------- | ---------------------------- | ------------------------------------------------------- |
| API / OSINT engines  | `backend/` (Flask, gunicorn) | Stateless JSON API. Real server → supports threaded scans. |
| UI                   | `frontend/` (HTML/CSS/JS)    | No build framework; a tiny build step injects the API URL. |
| Secrets / API keys   | Environment variables only   | Nothing is committed. See `backend/.env.example`.       |
| Cross-origin         | CORS allow-list (env)        | `ALLOWED_ORIGINS` on the backend.                       |

**Why split?** Vercel serverless is a poor fit for the long-running, threaded
username scans; Render gives the API a real, always-warm server. Vercel gives
the static frontend a global CDN with excellent Core Web Vitals. The two
communicate over a configurable API base URL — there are no hardcoded URLs in
application code.

---

## Features

**Reliable lookups (no API key required):**
- **Username** search across 100+ platforms with per-platform validators to cut
  false positives, plus parallel enrichment for avatars, bios, and follower counts.
- **Email intelligence** — provider/deliverability analysis (MX over DoH),
  disposable detection, Gravatar + linked accounts, and breach exposure (LeakCheck).
- **Domain / WHOIS** via RDAP (registrar, lifecycle dates, DNSSEC, nameservers).
- **DNS records** (A, AAAA, MX, NS, TXT, CNAME, SOA, CAA) over DNS-over-HTTPS.
- **IP geolocation** + network/ASN ownership, hosting/proxy flags, and reverse DNS.

**Platform:** dark/light theme, JSON/CSV export, browser-local search history,
loading & error states, rate limiting, and TTL caching.

**Optional (enabled by adding a key):** full-name & reverse-image search
(Google Programmable Search), Have I Been Pwned breach data, higher GitHub limits.

---

## Local development

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # optional; sensible defaults work without it
python app.py                 # serves http://localhost:5000
```

**Frontend**

```bash
cd frontend
python -m http.server 8000    # or any static server; serves http://localhost:8000
```

On `localhost`, the frontend automatically targets `http://localhost:5000`, and
the backend's dev CORS defaults already allow common localhost ports.

---

## Deployment

### Backend → Render

1. New **Blueprint** (or Web Service) pointing at this repo; root directory `backend`.
   `backend/render.yaml` is a ready-to-use blueprint.
2. Start command: `gunicorn wsgi:app --workers 2 --threads 8 --timeout 120 --bind 0.0.0.0:$PORT`
3. Set environment variables:
   - `FLASK_ENV=production`
   - `ALLOWED_ORIGINS=https://myrecon.xyz,https://www.myrecon.xyz`
   - `SECRET_KEY` (Render can generate it)
   - Optional: `GOOGLE_API_KEY`, `GOOGLE_CX_ID`, `HIBP_API_KEY`, `GITHUB_TOKEN`
4. Health check path: `/api/health`.

### Frontend → Vercel

1. New Project; root directory `frontend`. Framework preset: **Other**.
2. Add environment variable **`API_BASE_URL`** = your Render URL, e.g.
   `https://myrecon-api.onrender.com`. The build step (`scripts/gen-env.js`)
   injects it into the site — the URL is never hardcoded in source.
3. Point the `myrecon.xyz` domain at the Vercel project.

After both are live, make sure the Render `ALLOWED_ORIGINS` includes the exact
Vercel/custom-domain origin so CORS succeeds.

---

## Security notes

- All user input is validated and sanitized server-side (`backend/core/validation.py`).
- API endpoints are rate-limited per IP and protected by an origin allow-list.
- Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)
  are applied by both the API and Vercel.
- **Secrets live only in environment variables.**

> ⚠️ **Rotate old keys.** The pre-refactor `config.py` (see *Legacy cleanup*)
> committed live Google and SerpAPI keys in plaintext. Treat them as compromised
> and revoke/rotate them in the respective consoles.

---

## Legacy cleanup

The refactor left the original single-app/desktop code in place (it is no longer
used by either deployment). Once you've confirmed the new structure, you can
remove it:

```bash
# from the repo root
rm -f main.py web_main.py config.py vercel.json Procfile \
      requirements.txt requirements-desktop.txt
rm -rf gui assets web modules services utils data
```

Everything the app needs now lives under `backend/` and `frontend/`.
