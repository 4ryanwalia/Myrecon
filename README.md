# MyRecon: Username Search & OSINT Toolkit

**Open-source OSINT toolkit for authorized digital-footprint audits.** Check usernames, breach exposure, domains, DNS, and IPs with a web app, Python CLI, or Flask API.

Public username search · digital footprint audit · email breach checker · WHOIS and DNS lookup · IP intelligence

[Try the web app](https://myrecon.xyz) · [Offline demo](#try-the-verdict-demo) · [Run the CLI](#quick-start) · [Explore the API](#api) · [Contribute](CONTRIBUTING.md)

![MyRecon web app with a username lookup and an illustrative platform map](docs/web-home.png)

MyRecon is built for self-audits and authorized research. A shared username is not proof that two accounts belong to the same person.

## What problem are we solving?

Digital-footprint checks are often scattered across separate tools, and username search tools can mistake a block page, sign-in wall, or generic HTTP 200 response for proof that an account exists. That creates fragmented investigations and false confidence.

MyRecon brings public username signals, supported breach exposure checks, and domain/DNS/IP research into one web app, Python CLI, and API. Each username result is labeled `found`, `not_found`, or `unknown` according to the evidence available, so an inconclusive lookup stays inconclusive. It is designed for people auditing their own footprint and for authorized research using public sources.

## Username search and digital footprint tools

- **Evidence-aware username results.** A platform is marked `found` only with positive evidence, `not_found` with negative evidence, and `unknown` when a block, sign-in wall, timeout, or ambiguous page prevents a conclusion. An HTTP 200 response alone does not prove an account exists.
- **One place for your exposure checks.** Explore public breach data and email signals, inspect DNS and registration records, and review IP and hosting information.
- **Use the interface that fits.** Search in the browser, run a scriptable CLI locally, or integrate with the HTTP API. The website streams scan progress and supports JSON and CSV exports.

## Guides and measured benchmarks

[Username OSINT guide](https://www.myrecon.xyz/guides/username-osint-search.html) · [Platform profile lookups](https://www.myrecon.xyz/find/) · [Privacy guides](https://www.myrecon.xyz/privacy/) · [OSINT tool comparisons](https://www.myrecon.xyz/vs/)

The [public benchmark dashboard](https://www.myrecon.xyz/#benchmarks) publishes daily measurements for 10 fixed usernames across GitHub, GitLab and Hacker News. Inspect [raw runs and methodology](frontend/data/benchmarks.json) for timestamps, verdicts, coverage and unknown outcomes. This small regression sample shares API evidence with the engine; it is not an independent accuracy audit or a ranking against named OSINT tools.

## Try the verdict demo

See why a sign-in wall and a timeout stay `unknown`. After cloning this repository, run:

```bash
python examples/offline_demo.py
```

No dependencies, account, API key, or network needed. Four **synthetic examples** show `found`, `not_found`, and `unknown` with evidence and a suggested next step. This illustrates the verdict contract; it is not a live scan or accuracy benchmark. Use `--json` for labeled sample output, or [read the walkthrough](examples/README.md).

## Quick start

Try a username lookup in the [web app](https://myrecon.xyz), or run the CLI from a clone:

```bash
git clone https://github.com/4ryanwalia/Myrecon.git
cd Myrecon
python -m pip install -r backend/requirements.txt
python myrecon.py username yourhandle
```

Replace `yourhandle` with a username you own or have permission to investigate. The CLI checks 50 platforms by default; `--deep` checks 100. It runs the shared lookup services locally, without starting the web server.

```bash
python myrecon.py username yourhandle --deep
python myrecon.py domain example.com
python myrecon.py --help
```

![MyRecon terminal command menu](docs/cli-home.png)

## What is included?

| Capability | Website | CLI | Notes |
| --- | :---: | :---: | --- |
| Username sweep and profile evidence | Yes | Yes | The website currently has 561 standard catalogue entries. The CLI checks 50 or 100. |
| Extended username sweep | Yes | No | Opt-in paid Extended scan across 3,166 catalogue entries, including the standard set. |
| Email and breach exposure | Yes | Yes | Checks supported public sources; source availability can vary. |
| Domain, DNS, RDAP/WHOIS, IP, and certificate-transparency subdomains | Yes | Yes | Public infrastructure data. |
| Investigation graph and profile enrichment | Yes | Yes | Relationships are leads to verify, not identity claims. |
| Local image metadata and hashes | No | Yes | Reads a local file without uploading it; install `Pillow` and `numpy` for image decoding. |
| Place lookup from GPS coordinates | No | Yes | Uses public geodata sources to describe coordinates; it does not recognize landmarks in a picture. |
| Password exposure check | Yes | No | Hashes in the browser and sends only a hash prefix to Pwned Passwords. |
| Full-name and reverse-image web search | Yes | Yes | Requires Google Programmable Search credentials. |

**Website access:** Guests can run the standard 561-entry sweep but see the first 100 platform verdicts. Sign in for 5 free standard 500+ platform scans per UTC day and complete results. The only paid plan is ₹99 for unlimited standard scans plus 10 Extended 3,000+ platform scans, with no expiry. Paid standard access remains unlimited after Extended credits are used. Check the [current plans](https://myrecon.xyz/pricing.html) before purchasing. Other core lookups are available without an account.

The [Android app](https://myrecon.xyz/app.html) is maintained separately; its source is not in this repository.

## How username verdicts work

| Verdict | Meaning |
| --- | --- |
| `found` | The platform returned positive account evidence, such as a user object, profile marker, or a page that differs from a known missing-user control. |
| `not_found` | The platform returned negative evidence, such as a 404/410, a missing-user message, or the same page as a known missing-user control. |
| `unknown` | The platform blocked the request or did not provide enough evidence. This includes challenges, login walls, timeouts, and ambiguous redirects. |

Network conditions and platform behaviour change. Treat results as leads and verify important findings at the source. See [how to verify an OSINT finding](https://myrecon.xyz/guides/verify-an-osint-finding.html).

## Run the website locally

Start the API and static site in separate terminals after installing the backend requirements:

```bash
python myrecon.py serve
```

```bash
cd frontend
python -m http.server 8000
```

Open [http://localhost:8000](http://localhost:8000). The local frontend uses the API on `http://localhost:5000`. Guest lookups work without account configuration; sign-in and paid plans require Firebase and payment-provider settings.

## API

The Flask API lives in [`backend/`](backend/). For example, with the API running locally:

```bash
curl -X POST http://localhost:5000/api/dns -H "Content-Type: application/json" -d '{"domain":"example.com"}'
```

Selected routes include `POST /api/username`, `POST /api/username/stream`, `POST /api/email`, `POST /api/domain`, `POST /api/dns`, `POST /api/whois`, `POST /api/ip`, and `GET /api/health`. Streaming routes send newline-delimited JSON progress and completion events. See [`backend/app.py`](backend/app.py) for the complete route list, including account and plan endpoints.

## Project layout

| Path | Purpose |
| --- | --- |
| [`backend/modules/`](backend/modules/) | Public-source lookup engines and platform verdicts. |
| [`backend/services/`](backend/services/) | Service functions shared by the API and CLI. |
| [`backend/core/`](backend/core/) | Input validation, rate limits, caching, and request controls. |
| [`frontend/`](frontend/) | Static HTML, CSS, and JavaScript for the web app, guides, and breach archive. |
| [`cli/`](cli/) | CLI commands and terminal output. |
| [`backend/tests/`](backend/tests/) | Backend tests. |

The web frontend is deployed from Vercel using [`frontend/vercel.json`](frontend/vercel.json); the API has a Render blueprint at [`backend/render.yaml`](backend/render.yaml). The site also publishes [Breach Files](https://myrecon.xyz/breaches/) and [practical guides](https://myrecon.xyz/guides/).

## Configuration and tests

Core CLI lookups need no API key. Optional integrations and hosted account features use environment variables:

| Variables | Purpose |
| --- | --- |
| `GOOGLE_API_KEY`, `GOOGLE_CX_ID` | Full-name and reverse-image web search. |
| `GITHUB_TOKEN` | Higher GitHub API rate limit for public-source lookups. |
| `FIREBASE_SERVICE_ACCOUNT`, Firebase web configuration | Sign-in and persistent web account state. |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Extended scan pack checkout and webhook handling. |
| `API_BASE_URL` | API origin for the hosted frontend build. |

Keep credentials out of source control. To run the backend test suite:

```bash
python -m pip install pytest
python -m pytest backend/tests -q
```

## Contributing

Contributions are welcome. Read the [contribution guide](CONTRIBUTING.md) for setup, evidence requirements, and the maintainer approval process. Here are useful ways to help:

- **Improve platform coverage:** add or update a platform verdict check and include fixtures or a reproducible example that demonstrates the expected `found`, `not_found`, or `unknown` result.
- **Improve documentation:** clarify setup, API/CLI usage, or how to verify a finding. Keep examples safe to share and grounded in public sources.
- **Strengthen API and CLI tests:** cover a user-visible command or endpoint, including error and uncertain-result cases where relevant.

For substantial or behavior-changing work, open an [issue](https://github.com/4ryanwalia/Myrecon/issues) first to agree on scope. Then submit a focused pull request that links the issue, explains the change, and summarizes relevant test results. Do not include personal lookup results, private data, or API keys. Every pull request requires explicit approval from the project maintainer before merge; submission does not guarantee acceptance.

If MyRecon helps you understand your footprint, [star the repository](https://github.com/4ryanwalia/Myrecon) to help others discover it.

## Security

Do not commit credentials or personal scan results. Earlier repository history included plaintext keys in a legacy configuration file. Treat those keys as compromised and rotate or revoke them; removing a file does not erase Git history.

## License

The code is released under the [MIT License](LICENSE). The MyRecon name and logo are not granted under that license. Third-party data remains subject to its providers' terms.
