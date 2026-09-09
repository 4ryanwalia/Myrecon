/* Breach Files — static article generator.
 *
 * Builds /breaches/ from Have I Been Pwned's public breach catalogue: one
 * article per tracked breach, an index with the running totals and a
 * year-by-year view, and a JSON feed the Android app reads later.
 *
 * WHY IT IS BUILT RATHER THAN FETCHED
 * The obvious version calls HIBP from the browser — the API is keyless and
 * sends Access-Control-Allow-Origin: *, so it would work. It would also ship
 * a megabyte to every visitor and leave the articles invisible to search
 * engines, which for a page whose whole purpose is to be found and read is
 * the wrong trade. Generating real pages costs one build and earns indexing.
 *
 * WHAT IS OURS AND WHAT IS NOT
 * HIBP's breach data is licensed CC BY 4.0, so its description may be
 * republished with attribution — and every page does attribute it, in the
 * article body rather than buried in a footer. Everything around that
 * description is generated here from the structured fields: the severity
 * score, what each leaked data class means for a person, the scale
 * comparison, the timeline, and what to do now. No language model is
 * involved anywhere; every sentence is derived from a number or a flag in
 * the record, so nothing can drift from the evidence.
 *
 * Where a hand-written take exists in content/breaches/<Name>.html it is
 * placed above the generated analysis under a clear byline. That is the seam
 * for editorial: write one when a breach deserves it, leave it alone
 * otherwise, and the page still stands up.
 *
 * Run: node scripts/build-breaches.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "breaches");
const DATA_DIR = path.join(ROOT, "assets", "data");
const EDITORIAL_DIR = path.join(ROOT, "content", "breaches");

const SITE = "https://myrecon.xyz";
const SOURCE = "https://haveibeenpwned.com/api/v3/breaches";
const LICENCE = "https://creativecommons.org/licenses/by/4.0/";

/** How far back the archive reaches. */
const YEARS = 5;

/**
 * The seed set: ten breaches to open the archive with.
 *
 * Split rather than simply "the ten biggest", because the ten biggest are
 * almost entirely credential dumps and stealer-log collections — enormous,
 * genuinely important, and completely faceless. There is no company to name,
 * no incident to describe and no logo to show, so ten of those makes an
 * archive nobody wants to read. Weighting toward named companies gives the
 * archive the thing it is for: a story with somebody in it. The largest
 * aggregates still get their slots, because leaving out the biggest exposures
 * on record to make the page prettier would be its own kind of dishonesty.
 */
const SEED_NAMED_TOTAL = 10;
const SEED_AGGREGATE = 2;

/**
 * Everything HIBP publishes from this date onward gets an article.
 *
 * Keyed on AddedDate, not BreachDate: a breach from 2021 disclosed next month
 * is news next month. Older material stays out unless it made the seed set,
 * which is what keeps the archive a curated thing rather than a dump.
 */
const TRACK_ADDED_SINCE = "2026-09-07";

// ── Analysis ─────────────────────────────────────────────────────

/**
 * What each leaked field actually costs the person it belongs to.
 *
 * `weight` drives the severity score; `why` is printed verbatim. Both are
 * deliberately about consequences rather than categories — "passwords were
 * exposed" tells a reader nothing they can act on, and "anyone who reused
 * that password elsewhere has those accounts exposed too" tells them exactly
 * what to go and do.
 */
const DATA_CLASSES = {
  "Passwords": { weight: 30, why: "Anyone reusing this password elsewhere has those accounts exposed too — credential stuffing is automated and tries them all within days." },
  "Historical passwords": { weight: 26, why: "Old passwords reveal the pattern people build new ones from, which makes the current one guessable." },
  "Auth tokens": { weight: 28, why: "A stolen session token can be used without ever knowing the password, and password changes do not always invalidate it." },
  "Security questions and answers": { weight: 24, why: "These are reused across banks and email providers, and unlike a password almost nobody ever changes them." },
  "Password hints": { weight: 18, why: "A hint written by the account holder often gives the password away to anyone who knows a little about them." },
  "Social security numbers": { weight: 32, why: "A government identifier cannot be reissued on request. This is the raw material for opening credit in someone else's name." },
  "Government issued IDs": { weight: 30, why: "Passport and licence numbers are used to prove identity to banks and telecoms, and they are effectively permanent." },
  "Credit cards": { weight: 28, why: "Directly spendable until the card is cancelled, and card numbers circulate for years after a breach." },
  "Partial credit card data": { weight: 14, why: "Not enough to spend, but enough to convince a victim that a caller is genuinely from their bank." },
  "Payment histories": { weight: 14, why: "Shows what someone buys and from whom — the detail that makes a phishing message land." },
  "Bank account numbers": { weight: 26, why: "Enables direct-debit fraud and gives a caller the detail needed to sound like the bank." },
  "Health insurance information": { weight: 24, why: "Medical identity fraud is slow to detect and hard to unwind, and the data itself is sensitive for life." },
  "Private messages": { weight: 26, why: "Content nobody wrote expecting an audience. The damage here is not fraud, it is exposure." },
  "Sexual orientation": { weight: 28, why: "In some countries this information puts people in physical and legal danger, regardless of how the breach happened." },
  "Physical addresses": { weight: 20, why: "Where someone actually lives. Combined with a name this moves the risk off the internet." },
  "Phone numbers": { weight: 18, why: "Enables SIM-swap attacks against SMS two-factor codes, and puts the number on scam-call lists indefinitely." },
  "Dates of birth": { weight: 16, why: "One of the three things call centres ask to verify identity, and it never changes." },
  "Names": { weight: 10, why: "Turns an anonymous address into an identified person, which is what makes targeted phishing possible." },
  "Email addresses": { weight: 8, why: "The address becomes a confirmed, active target — expect more phishing, better aimed." },
  "Usernames": { weight: 8, why: "A handle links this account to every other place the same handle is used." },
  "IP addresses": { weight: 10, why: "Approximate location at the time of use, and a way to correlate accounts across services." },
  "Geographic locations": { weight: 12, why: "Where the account was used, which narrows a person down further than most people expect." },
  "Genders": { weight: 4, why: "Small on its own; useful to anyone assembling a fuller profile." },
  "Employers": { weight: 10, why: "Connects a personal account to a workplace, which is how attackers pivot from a person to a company." },
  "Job titles": { weight: 8, why: "Identifies who has access to what, which is how targets for business email compromise are picked." },
  "Bios": { weight: 6, why: "Self-written detail that often contains far more identifying information than people remember putting there." },
  "Browsing histories": { weight: 20, why: "A record of interests and habits that most people would consider private." },
  "Website activity": { weight: 12, why: "What was done on the site and when, which can be sensitive depending on the site." },
  "Device information": { weight: 8, why: "Fingerprints a device across services and helps an attacker imitate a trusted login." },
  "Purchases": { weight: 10, why: "What was bought and when — detail that makes an impersonation convincing." },
  "Physical attributes": { weight: 8, why: "Descriptive personal detail, sensitive in combination with a name and address." },
};

const DEFAULT_CLASS = { weight: 6, why: "Adds detail to a profile that can be assembled from several breaches at once." };

/** Rounded reference populations, for making a raw count mean something. */
const POPULATIONS = [
  ["the world", 8_100_000_000],
  ["India", 1_430_000_000],
  ["China", 1_420_000_000],
  ["the United States", 340_000_000],
  ["Brazil", 217_000_000],
  ["Russia", 144_000_000],
  ["Japan", 124_000_000],
  ["Germany", 84_000_000],
  ["the United Kingdom", 68_000_000],
  ["Canada", 40_000_000],
  ["Australia", 27_000_000],
];

/**
 * Severity, 0–100.
 *
 * Three parts: how many people, how damaging the specific fields are, and
 * whether the breach is confirmed. Scale is logarithmic because the step from
 * ten thousand to a million matters far more than a million to two, and the
 * sensitivity term uses diminishing returns so a long list of minor fields
 * can never outweigh one catastrophic one.
 */
function severity(b) {
  const count = Math.max(b.PwnCount || 0, 1);
  const scale = Math.min(45, Math.max(0, (Math.log10(count) - 4) * 9));

  const weights = (b.DataClasses || [])
    .map((c) => (DATA_CLASSES[c] || DEFAULT_CLASS).weight)
    .sort((a, z) => z - a);
  const sensitivity = Math.min(
    40,
    weights.reduce((sum, w, i) => sum + w * Math.pow(0.55, i), 0),
  );

  let flags = 0;
  if (b.IsVerified) flags += 5;
  if (b.IsSensitive) flags += 5;
  if (b.IsMalware || b.IsStealerLog) flags += 5;

  const score = Math.round(Math.min(100, scale + sensitivity + flags));
  const band =
    score >= 80 ? "Critical" : score >= 60 ? "Severe" : score >= 40 ? "Serious" : "Moderate";
  return { score, band };
}

/** Put a raw account count into human terms. */
function scaleLine(count) {
  if (!count) return null;
  for (const [place, pop] of POPULATIONS) {
    if (count >= pop) {
      const times = count / pop;
      if (times >= 1.5) {
        return `That is about ${times.toFixed(1)}× the population of ${place}.`;
      }
      return `That is roughly everyone in ${place}.`;
    }
  }
  const [place, pop] = POPULATIONS[POPULATIONS.length - 1];
  const share = Math.round((count / pop) * 100);
  if (share >= 5) return `That is about ${share}% of the population of ${place}.`;
  return null;
}

/**
 * What the reader should actually do, derived from what leaked.
 *
 * Ordered by urgency and de-duplicated, because advice that lists everything
 * is advice nobody follows.
 */
function actions(b) {
  const has = (c) => (b.DataClasses || []).includes(c);
  const out = [];

  if (has("Passwords") || has("Historical passwords")) {
    out.push("Change this password anywhere you reused it, starting with your email account — that is the one that can reset all the others.");
  }
  if (has("Auth tokens")) {
    out.push("Sign out of all sessions in the account's security settings. Changing a password does not always kill an existing session.");
  }
  if (has("Security questions and answers") || has("Password hints")) {
    out.push("Change your security answers on other sites too. Treat them as passwords, and there is no rule that says they have to be true.");
  }
  if (has("Phone numbers")) {
    out.push("Move two-factor authentication off SMS and onto an authenticator app, which a SIM swap cannot intercept.");
  }
  if (has("Credit cards") || has("Bank account numbers") || has("Payment histories")) {
    out.push("Check statements for the months after the breach date and ask your bank for a replacement card if the number was full.");
  }
  if (has("Social security numbers") || has("Government issued IDs")) {
    out.push("Consider a credit freeze. A government identifier cannot be changed, so limiting what can be opened in your name is the only real control.");
  }
  if (has("Physical addresses")) {
    out.push("Be sceptical of post and callers who already know your address — knowing it is no longer evidence of anything.");
  }
  out.push("Expect better-aimed phishing. A message that already knows your name and where you have an account is the whole point of a breach like this.");
  return out;
}


/**
 * Guides worth linking from a breach, chosen by what leaked.
 *
 * Internal links only earn anything when the anchor describes the
 * destination and the destination genuinely follows from the page. Keying
 * them on the data classes does both: a breach that exposed passwords links
 * to the password guide because that is the next thing that reader needs,
 * not because a template had a slot for it.
 */
const CLASS_GUIDES = [
  ["Passwords", "/guides/strong-passwords-guide.html", "how to build passwords that survive a breach"],
  ["Historical passwords", "/guides/strong-passwords-guide.html", "how to build passwords that survive a breach"],
  ["Phone numbers", "/guides/two-factor-authentication.html", "why SMS two-factor is the weakest kind"],
  ["Auth tokens", "/guides/two-factor-authentication.html", "why SMS two-factor is the weakest kind"],
  ["Email addresses", "/guides/how-to-spot-phishing.html", "how to spot the phishing that follows a breach"],
  ["Physical addresses", "/guides/reduce-your-digital-footprint.html", "how to reduce what is public about you"],
  ["Names", "/guides/how-data-brokers-work.html", "how data brokers turn a leak into a profile"],
  ["Usernames", "/guides/username-osint-search.html", "what a single username reveals across platforms"],
];

function guideLinks(b) {
  const seen = new Set();
  const out = [];
  (b.DataClasses || []).forEach((c) => {
    const hit = CLASS_GUIDES.find((g) => g[0] === c);
    if (hit && !seen.has(hit[1])) {
      seen.add(hit[1]);
      out.push(hit);
    }
  });
  if (!seen.has("/guides/check-email-data-breach.html")) {
    out.push(["", "/guides/check-email-data-breach.html", "how to check whether your email is in a breach"]);
  }
  return out.slice(0, 4);
}

// ── Selection ────────────────────────────────────────────────────

function withinWindow(b, cutoffISO) {
  return (b.BreachDate || "") >= cutoffISO;
}

function select(all) {
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() - YEARS);
  const cutoffISO = cutoff.toISOString().slice(0, 10);

  const window = all
    .filter((b) => withinWindow(b, cutoffISO))
    .filter((b) => !b.IsFabricated && !b.IsRetired);

  const biggest = (list) => [...list].sort((a, b) => (b.PwnCount || 0) - (a.PwnCount || 0));

  // A breach with a domain of its own is an incident at an identifiable
  // organisation; everything else is an aggregate someone assembled.
  const isNamed = (b) => !!b.Domain && !b.IsStealerLog && !b.IsSpamList;

  // Spread the seed across the window rather than taking the ten biggest
  // outright. Ranked purely by size the archive collapses into the last two
  // years — recent aggregates dwarf everything before them — and an archive
  // that claims five years while showing two is not an archive. Two named
  // breaches per year covers the span and keeps every entry a company with a
  // story attached.
  const thisYear = new Date().getFullYear();
  const perYear = Math.max(1, Math.round(SEED_NAMED_TOTAL / YEARS));
  const named = [];
  for (let y = thisYear; y > thisYear - YEARS; y -= 1) {
    const inYear = window.filter((b) => isNamed(b) && (b.BreachDate || "").startsWith(String(y)));
    named.push(...biggest(inYear).slice(0, perYear));
  }

  // The largest aggregates still earn their slots. They are faceless, but
  // they are also the biggest exposures on record, and dropping them to make
  // the page tidier would misrepresent the scale of the problem.
  const aggregate = biggest(window.filter((b) => !isNamed(b))).slice(0, SEED_AGGREGATE);

  // From the cutoff onward everything is covered, whichever kind it is —
  // curation applies to the back catalogue, not to the news.
  const fresh = window.filter((b) => (b.AddedDate || "").slice(0, 10) >= TRACK_ADDED_SINCE);

  const byName = new Map();
  [...named, ...aggregate, ...fresh].forEach((b) => byName.set(b.Name, b));
  return [...byName.values()].sort((a, b) => (b.BreachDate || "").localeCompare(a.BreachDate || ""));
}

// ── Rendering ────────────────────────────────────────────────────

const esc = (s) =>
  String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const slug = (s) =>
  String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

const num = (n) => Number(n || 0).toLocaleString("en-GB");

function prettyDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

/**
 * HIBP descriptions contain anchors and paragraph markup by design.
 *
 * They are allowed through, but only those tags: the field is third-party
 * content rendered into our pages, and a permissive pass-through of arbitrary
 * HTML from any upstream source is how a content pipeline becomes an XSS
 * vector. Everything else is escaped.
 */
function sanitise(html) {
  if (!html) return "";
  const allowed = /^<\/?(?:a|b|strong|i|em|p|br|ul|ol|li)(?:\s[^<>]*)?>$/i;
  return String(html).replace(/<[^>]*>/g, (tag) => {
    if (!allowed.test(tag)) return "";
    if (/^<a\s/i.test(tag)) {
      const href = /href\s*=\s*["']([^"']*)["']/i.exec(tag);
      const url = href && /^https?:\/\//i.test(href[1]) ? href[1] : null;
      return url
        ? `<a href="${esc(url)}" target="_blank" rel="noopener nofollow">`
        : "<span>";
    }
    return tag;
  });
}

const HEAD = (opts) => `<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${esc(opts.title)}</title>
  <meta name="description" content="${esc(opts.description)}">
  <meta name="robots" content="index, follow">
  <meta name="theme-color" content="#0a0f1a">
  <link rel="canonical" href="${esc(opts.url)}">
  <meta property="og:type" content="${opts.ogType || "website"}">
  <meta property="og:title" content="${esc(opts.title)}">
  <meta property="og:description" content="${esc(opts.description)}">
  <meta property="og:url" content="${esc(opts.url)}">
  <meta property="og:image" content="${esc(opts.image || SITE + "/assets/img/og-image.png")}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/svg+xml" href="/assets/img/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/styles.css?v=8">
  <link rel="stylesheet" href="/assets/css/breaches.css?v=1">
  <meta name="google-adsense-account" content="ca-pub-6109270472398539">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6109270472398539" crossorigin="anonymous"></script>
${opts.jsonLd ? `  <script type="application/ld+json">${opts.jsonLd}</script>\n` : ""}${opts.extraLd ? `  <script type="application/ld+json">${opts.extraLd}</script>\n` : ""}  <link rel="alternate" type="application/rss+xml" title="MyRecon — The Breach Files" href="${SITE}/breaches/feed.xml">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="nav">
    <div class="container nav-inner">
      <a class="brand" href="/" aria-label="MyRecon home"><img class="logo" src="/assets/img/logo.svg" alt="" width="32" height="32"> MyRecon <small>OSINT</small></a>
      <nav class="nav-links" id="navLinks" aria-label="Primary"><a href="/#tool">Tool</a><a href="/services.html">Services</a><a href="/breaches/">Breaches</a><a href="/guides/">Guides</a><a href="/app.html">App</a><a href="/about.html">About</a></nav>
      <button class="icon-btn" id="themeToggle" type="button" aria-label="Toggle theme"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" stroke-linejoin="round"/></svg></button>
      <button class="icon-btn nav-toggle" id="navToggle" type="button" aria-label="Toggle menu"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round"/></svg></button>
    </div>
  </header>
`;

const FOOT = `
  <footer class="footer">
    <div class="container"><div class="footer-bottom">
      <span>&copy; 2026 MyRecon · myrecon.xyz</span>
      <span><a href="/breaches/" style="color:var(--text-dim)">Breaches</a> · <a href="/guides/" style="color:var(--text-dim)">Guides</a> · <a href="/privacy.html" style="color:var(--text-dim)">Privacy</a></span>
    </div></div>
  </footer>
  <script src="/assets/js/env.js?v=8"></script>
  <script src="/assets/js/config.js?v=8"></script>
  <script src="/assets/js/app.js?v=8"></script>
  <script src="/assets/js/breach-check.js?v=1"></script>
</body>
</html>
`;

const bandClass = (band) => "sev-" + band.toLowerCase();

function logoFor(b) {
  // HIBP serves a generic list icon for collections that are not one company.
  const p = b.LogoPath || "";
  return p && !/List\.png$/i.test(p) ? p : null;
}

function article(b, editorial, siblings) {
  const sev = severity(b);
  const url = `${SITE}/breaches/${slug(b.Name)}.html`;
  const logo = logoFor(b);
  const classes = (b.DataClasses || []).map((c) => ({
    name: c,
    why: (DATA_CLASSES[c] || DEFAULT_CLASS).why,
  }));
  const scale = scaleLine(b.PwnCount);
  const acts = actions(b);
  const year = (b.BreachDate || "").slice(0, 4);

  const lead =
    `On ${prettyDate(b.BreachDate)}, ${b.Title} was breached. ` +
    `${num(b.PwnCount)} accounts were exposed` +
    (classes.length
      ? `, including ${classes.slice(0, 3).map((c) => c.name.toLowerCase()).join(", ")}`
      : "") +
    `. MyRecon rates it ${sev.score}/100 — ${sev.band.toLowerCase()}.`;

  const crumbs = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "MyRecon", item: SITE },
      { "@type": "ListItem", position: 2, name: "The Breach Files", item: `${SITE}/breaches/` },
      { "@type": "ListItem", position: 3, name: b.Title, item: url },
    ],
  });

  const jsonLd = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: `${b.Title} data breach — ${num(b.PwnCount)} accounts exposed`,
    description: lead,
    datePublished: (b.AddedDate || b.BreachDate || "").slice(0, 10),
    dateModified: (b.ModifiedDate || b.AddedDate || "").slice(0, 10),
    author: { "@type": "Organization", name: "MyRecon" },
    publisher: { "@type": "Organization", name: "MyRecon" },
    mainEntityOfPage: url,
    ...(logo ? { image: logo } : {}),
  });

  const related = siblings
    .filter((s) => s.Name !== b.Name)
    .slice(0, 3)
    .map(
      (s) =>
        `<li><a href="/breaches/${slug(s.Name)}.html">${esc(s.Title)}</a> — ${num(s.PwnCount)} accounts</li>`,
    )
    .join("");

  return (
    HEAD({
      title: `${b.Title} data breach: ${num(b.PwnCount)} accounts exposed — MyRecon`,
      description: lead.slice(0, 180),
      url,
      ogType: "article",
      image: logo || undefined,
      jsonLd,
      extraLd: crumbs,
    }) +
`  <main id="main" class="container">
    <article class="article breach-article">
      <p class="bx-crumb"><a href="/breaches/">← The Breach Files</a></p>

      <header class="bx-head">
        ${logo ? `<img class="bx-logo" src="${esc(logo)}" alt="" width="72" height="72" loading="lazy">` : ""}
        <div>
          <span class="kicker">${esc(year)} · Data breach</span>
          <h1>${esc(b.Title)}</h1>
          <p class="meta">Breached ${esc(prettyDate(b.BreachDate))} · Published ${esc(prettyDate(b.AddedDate))}${b.Domain ? ` · ${esc(b.Domain)}` : ""}</p>
        </div>
      </header>

      <div class="bx-stats">
        <div class="bx-stat"><b>${num(b.PwnCount)}</b><span>Accounts exposed</span></div>
        <div class="bx-stat ${bandClass(sev.band)}"><b>${sev.score}/100</b><span>${esc(sev.band)} severity</span></div>
        <div class="bx-stat"><b>${classes.length}</b><span>Types of data</span></div>
        <div class="bx-stat"><b>${b.IsVerified ? "Verified" : "Unverified"}</b><span>By HIBP</span></div>
      </div>

      <p class="lead">${esc(lead)}${scale ? " " + esc(scale) : ""}</p>

      <!-- Above the fold on purpose. Someone arriving from "was my email in
           the X breach" wants the answer, not a link to it further down. -->
      <form class="bx-check" data-breach-check>
        <label for="bxEmail">Was your address in this breach?</label>
        <div class="bx-check-row">
          <input id="bxEmail" type="email" name="email" inputmode="email" autocomplete="email"
                 placeholder="you@example.com" required>
          <button class="btn btn-sm" type="submit">Check free</button>
        </div>
        <p class="bx-check-note">Checked against this breach and every other on record. Your address is not stored, and the check runs against public breach data only.</p>
      </form>

${editorial ? `      <section class="bx-editorial">
        <span class="bx-byline">MyRecon's take</span>
${editorial}
      </section>\n` : ""}
      <h2>What happened</h2>
      <div class="bx-source">
        <p>${sanitise(b.Description)}</p>
        <p class="bx-credit">Breach description from <a href="https://haveibeenpwned.com/PwnedWebsites#${esc(b.Name)}" target="_blank" rel="noopener">Have I Been Pwned</a>, used under a <a href="${LICENCE}" target="_blank" rel="noopener">CC BY 4.0 licence</a>.${b.Attribution ? ` Data provided to HIBP by ${esc(b.Attribution)}.` : ""}</p>
      </div>
${b.DisclosureUrl ? `      <p><a class="btn btn-ghost btn-sm" href="${esc(b.DisclosureUrl)}" target="_blank" rel="noopener nofollow">Read the original disclosure ↗</a></p>\n` : ""}
      <h2>Who was behind it</h2>
      <p>No party has been publicly confirmed as responsible, and this page will not name one. Most breaches are never formally attributed: data surfaces on a forum or inside a combined dump long after the intrusion, and the trail back to a specific actor is rarely made public. Where a group has claimed responsibility it is usually named in the account above — that claim is theirs, not a finding of ours.${
        b.IsStealerLog
          ? " These records came from information-stealing malware on victims' own machines rather than from one company's servers, so the exposure follows the person, not the site."
          : b.IsSpamList
            ? " This entry is a marketing list rather than a break-in: the data was aggregated and traded, which is legal in more places than most people assume."
            : ""
      }</p>

      <h2>What was exposed, and why it matters</h2>
      <ul class="bx-classes">
${classes.map((c) => `        <li><b>${esc(c.name)}</b><span>${esc(c.why)}</span></li>`).join("\n")}
      </ul>

      <h2>What to do if you were in it</h2>
      <ol class="bx-actions">
${acts.map((a) => `        <li>${esc(a)}</li>`).join("\n")}
      </ol>

      <!-- After the advice, never before it. The reader has just been told
           what to do; this is for the ones who read that list and realised
           they do not actually know where all their accounts are. -->
      <aside class="bx-offer">
        <h3>Not sure where all your accounts are?</h3>
        <p>Most people have a decade of forgotten signups behind an old address, plus data-broker listings they never created in the first place. We find them by hand, confirm which are genuinely yours, and work through getting them removed.</p>
        <p class="bx-offer-note">A paid service, and only ever on identifiers you own and can verify.</p>
        <p><a class="btn btn-sm" href="/services.html">See what a personal report covers →</a></p>
      </aside>

      <h2>Questions people ask about this breach</h2>
      <div class="bx-faq">
        <h3>Was my email address in the ${esc(b.Title)} breach?</h3>
        <p>Enter it in the box at the top of this page. MyRecon checks it against this breach and every other one on record, and the address is never stored.</p>

        <h3>What data was leaked in the ${esc(b.Title)} breach?</h3>
        <p>${classes.length ? esc(classes.map((c) => c.name.toLowerCase()).join(", ")) + "." : "No field list has been published for this breach."} ${classes.length ? "Each one is explained above, along with what it means for the person it belongs to." : ""}</p>

        <h3>When did it happen, and when did it become public?</h3>
        <p>The breach is dated ${esc(prettyDate(b.BreachDate))}. It was published to Have I Been Pwned on ${esc(prettyDate(b.AddedDate))}${
          b.BreachDate && b.AddedDate && b.AddedDate.slice(0, 10) > b.BreachDate
            ? `, a gap of ${Math.round((new Date(b.AddedDate) - new Date(b.BreachDate)) / 86400000)} days during which the data was already out`
            : ""
        }.</p>

        <h3>Is the ${esc(b.Title)} breach real?</h3>
        <p>${b.IsVerified
          ? "Yes. Have I Been Pwned lists it as verified, meaning the data was checked against the source rather than taken on trust."
          : "It is listed as unverified. The data exists and has been indexed, but it has not been confirmed against the named source, so treat the origin as unproven."}</p>

        <h3>How many people were affected?</h3>
        <p>${num(b.PwnCount)} accounts.${scale ? " " + esc(scale) : ""} That is accounts rather than people — one person often has several.</p>
      </div>

${guideLinks(b).length ? `      <h2>Read next</h2>
      <ul class="bx-related">
${guideLinks(b).map((g) => `        <li><a href="${g[1]}">${esc(g[2].charAt(0).toUpperCase() + g[2].slice(1))}</a></li>`).join("\n")}
      </ul>\n` : ""}

${related ? `      <h2>Also in the archive</h2>\n      <ul class="bx-related">${related}</ul>\n` : ""}
      <p class="bx-method">Severity is scored by MyRecon from the number of accounts, the sensitivity of the specific fields exposed, and whether the breach is confirmed — not by a language model. The description above is quoted from Have I Been Pwned; the analysis around it is ours.</p>

      <p style="margin-top:28px"><a class="btn btn-ghost" href="/breaches/">← All breaches</a></p>
    </article>
  </main>` +
    FOOT
  );
}

function index(items) {
  const total = items.reduce((s, b) => s + (b.PwnCount || 0), 0);
  const byYear = new Map();
  items.forEach((b) => {
    const y = (b.BreachDate || "").slice(0, 4);
    if (!y) return;
    const cur = byYear.get(y) || { count: 0, accounts: 0 };
    cur.count += 1;
    cur.accounts += b.PwnCount || 0;
    byYear.set(y, cur);
  });
  const years = [...byYear.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  const peak = Math.max(1, ...years.map(([, v]) => v.accounts));

  const url = `${SITE}/breaches/`;
  const description =
    `Data breach archive: what was taken, from whom, how many people it touched and what to do about it. ` +
    `${num(total)} accounts across ${items.length} breaches, updated daily.`;

  return (
    HEAD({
      title: "The Breach Files — data breach archive | MyRecon",
      description,
      url,
      jsonLd: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: "The Breach Files",
        description,
        url,
      }),
    }) +
`  <main id="main" class="section">
    <div class="container bx-page">
      <span class="kicker">The Breach Files</span>
      <h1 class="bx-title">Every breach worth understanding</h1>
      <p class="sub">Who was hit, what was taken, how many people it reached — and what it means for you. Built from public breach records and updated every day.</p>

      <div class="bx-summary">
        <div class="bx-stat"><b>${num(total)}</b><span>Accounts exposed</span></div>
        <div class="bx-stat"><b>${items.length}</b><span>Breaches in the archive</span></div>
        <div class="bx-stat"><b>${years.length}</b><span>Years covered</span></div>
      </div>

${years.length ? `      <h2 class="bx-h2">By year</h2>
      <div class="bx-years">
${years
  .map(
    ([y, v]) => `        <div class="bx-year">
          <span class="bx-year-label">${esc(y)}</span>
          <div class="bx-year-track"><div class="bx-year-fill" style="width:${Math.max(2, Math.round((v.accounts / peak) * 100))}%"></div></div>
          <span class="bx-year-value">${num(v.accounts)}</span>
        </div>`,
  )
  .join("\n")}
      </div>\n` : ""}
      <h2 class="bx-h2">The archive</h2>
      <div class="bx-grid">
${items
  .map((b) => {
    const sev = severity(b);
    const logo = logoFor(b);
    return `        <a class="bx-card" href="/breaches/${slug(b.Name)}.html">
          <div class="bx-card-head">
            ${logo ? `<img src="${esc(logo)}" alt="" width="40" height="40" loading="lazy">` : `<span class="bx-card-mark">${esc((b.Title || "?").slice(0, 2).toUpperCase())}</span>`}
            <div>
              <b>${esc(b.Title)}</b>
              <span>${esc(prettyDate(b.BreachDate))}</span>
            </div>
          </div>
          <p class="bx-card-count">${num(b.PwnCount)} <span>accounts</span></p>
          <p class="bx-card-classes">${esc((b.DataClasses || []).slice(0, 4).join(" · "))}</p>
          <span class="bx-badge ${bandClass(sev.band)}">${esc(sev.band)} · ${sev.score}</span>
        </a>`;
  })
  .join("\n")}
      </div>

      <p class="bx-method">Breach records come from <a href="https://haveibeenpwned.com" target="_blank" rel="noopener">Have I Been Pwned</a> and are used under a <a href="${LICENCE}" target="_blank" rel="noopener">CC BY 4.0 licence</a>. Severity scoring, the analysis of what each field means, and everything else on these pages is MyRecon's own and is generated from the records rather than written by a language model.</p>
    </div>
  </main>` +
    FOOT
  );
}


/**
 * RSS.
 *
 * Breach coverage is a news beat, and news beats get syndicated. A feed costs
 * nothing to emit and is the difference between waiting to be discovered and
 * being pulled in by every reader and aggregator that already follows this
 * subject.
 */
function rssFeed(items) {
  const now = new Date().toUTCString();
  const entries = items
    .slice(0, 40)
    .map((b) => {
      const sev = severity(b);
      const link = `${SITE}/breaches/${slug(b.Name)}.html`;
      const summary =
        `${num(b.PwnCount)} accounts exposed. Severity ${sev.score}/100 (${sev.band}). ` +
        `Data exposed: ${(b.DataClasses || []).join(", ") || "not published"}.`;
      return `    <item>
      <title>${esc(b.Title)} data breach — ${num(b.PwnCount)} accounts exposed</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${new Date(b.AddedDate || b.BreachDate || Date.now()).toUTCString()}</pubDate>
      <description>${esc(summary)}</description>
    </item>`;
    })
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>MyRecon — The Breach Files</title>
    <link>${SITE}/breaches/</link>
    <atom:link href="${SITE}/breaches/feed.xml" rel="self" type="application/rss+xml"/>
    <description>Data breach coverage: who was hit, what was taken, how many people it reached and what to do about it.</description>
    <language>en-GB</language>
    <lastBuildDate>${now}</lastBuildDate>
${entries}
  </channel>
</rss>
`;
}

// ── Build ────────────────────────────────────────────────────────

function readEditorial(name) {
  const file = path.join(EDITORIAL_DIR, `${name}.html`);
  if (!fs.existsSync(file)) return null;
  const body = fs.readFileSync(file, "utf8").trim();
  return body || null;
}

async function main() {
  const res = await fetch(SOURCE, {
    headers: {
      "User-Agent": "MyRecon-BreachFiles/1.0 (+https://myrecon.xyz)",
      Accept: "application/json",
    },
  });
  if (!res.ok) throw new Error(`HIBP returned HTTP ${res.status}`);
  const all = await res.json();

  const items = select(all);
  if (!items.length) throw new Error("no breaches selected — refusing to publish an empty archive");

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.mkdirSync(EDITORIAL_DIR, { recursive: true });

  let edited = 0;
  items.forEach((b) => {
    const editorial = readEditorial(b.Name);
    if (editorial) edited += 1;
    fs.writeFileSync(
      path.join(OUT_DIR, `${slug(b.Name)}.html`),
      article(b, editorial, items),
      "utf8",
    );
  });
  fs.writeFileSync(path.join(OUT_DIR, "index.html"), index(items), "utf8");
  fs.writeFileSync(path.join(OUT_DIR, "feed.xml"), rssFeed(items), "utf8");

  // The feed the Android app reads. Everything the article shows, so a client
  // never has to reproduce the scoring or re-fetch from HIBP.
  const feed = {
    generated: new Date().toISOString(),
    source: "Have I Been Pwned",
    licence: LICENCE,
    total_accounts: items.reduce((s, b) => s + (b.PwnCount || 0), 0),
    breaches: items.map((b) => {
      const sev = severity(b);
      return {
        name: b.Name,
        title: b.Title,
        slug: slug(b.Name),
        url: `${SITE}/breaches/${slug(b.Name)}.html`,
        domain: b.Domain || null,
        breach_date: b.BreachDate,
        added_date: b.AddedDate,
        accounts: b.PwnCount || 0,
        data_classes: b.DataClasses || [],
        verified: !!b.IsVerified,
        sensitive: !!b.IsSensitive,
        stealer_log: !!b.IsStealerLog,
        logo: logoFor(b),
        severity: sev.score,
        band: sev.band,
        // Who supplied the records to HIBP — a requested credit, not blame.
        data_provider: b.Attribution || null,
        summary: sanitise(b.Description).replace(/<[^>]*>/g, "").slice(0, 400),
      };
    }),
  };
  fs.writeFileSync(path.join(DATA_DIR, "breaches.json"), JSON.stringify(feed, null, 2), "utf8");

  updateSitemap(items);

  console.log(
    `[breaches] ${items.length} articles (${edited} with an editorial take), ` +
      `${num(feed.total_accounts)} accounts, feed written`,
  );
}

/**
 * Keep sitemap.xml in step.
 *
 * Rewrites only the block between the markers, so hand-maintained entries
 * around it survive a rebuild.
 */
function updateSitemap(items) {
  const file = path.join(ROOT, "sitemap.xml");
  if (!fs.existsSync(file)) return;
  const START = "<!-- breaches:start -->";
  const END = "<!-- breaches:end -->";
  const today = new Date().toISOString().slice(0, 10);

  const block =
    `${START}\n` +
    `  <url><loc>${SITE}/breaches/</loc><lastmod>${today}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>\n` +
    items
      .map(
        (b) =>
          `  <url><loc>${SITE}/breaches/${slug(b.Name)}.html</loc><lastmod>${(b.ModifiedDate || b.AddedDate || today).slice(0, 10)}</lastmod><priority>0.6</priority></url>`,
      )
      .join("\n") +
    `\n  ${END}`;

  let xml = fs.readFileSync(file, "utf8");
  if (xml.includes(START) && xml.includes(END)) {
    xml = xml.replace(new RegExp(`${START}[\\s\\S]*?${END}`), block);
  } else {
    xml = xml.replace("</urlset>", `  ${block}\n</urlset>`);
  }
  // .gitattributes normalises the repo to LF; writing CRLF back would show the
  // whole file as changed on every build.
  fs.writeFileSync(file, xml.replace(/\r\n/g, "\n"), "utf8");
}

main().catch((err) => {
  console.error(`[breaches] ${err.message}`);
  // A failed fetch must not take the whole site build down — the previously
  // generated pages are still on disk and still correct.
  process.exit(fs.existsSync(path.join(OUT_DIR, "index.html")) ? 0 : 1);
});
