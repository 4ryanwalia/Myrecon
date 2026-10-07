/* Keep the username checker landing page in the production static build. */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const site = 'https://www.myrecon.xyz';
const title = 'Username Checker & Social Media Username Search | MyRecon';
const description = 'Check public usernames across 500+ platforms with MyRecon. Review social media profile leads, unknown results and username availability limits.';
const url = `${site}/username-checker.html`;
const questions = [
  ['What is a username checker?', 'A username checker searches supported services for public profiles using a handle. MyRecon returns profile leads for source review. A matching handle does not prove who owns an account.'],
  ['Can I check username availability with MyRecon?', 'MyRecon checks public profile presence. A not-found result does not guarantee that a username is available to register. A platform may reserve a name, suspend an account or restrict its visibility. Confirm availability in the official signup or account settings flow.'],
  ['Is the username checker free?', 'MyRecon offers free guest previews. Sign in to access the results available to your account. Paid plans add features such as Deep Search and Extended scans; check the current pricing page for limits.'],
  ['Can I search every social media platform?', 'No. MyRecon checks a supported catalogue of more than 500 platforms, not every website. Login walls, anti-bot controls, timeouts and platform changes can leave a check unknown.'],
  ['How do I find my old accounts by username?', 'Search handles you remember using, then open each candidate profile and compare it with your own records. Use saved passwords, signup emails and the official account recovery process to confirm ownership.'],
];
const body = `<main id="main" class="container prose discovery-page">
  <nav aria-label="Breadcrumb"><a href="/">MyRecon</a> / Username checker</nav>
  <h1>Username checker and social media username search</h1>
  <p class="sub">MyRecon searches a public username across a supported catalogue of 500+ platforms. Use it to review your own digital footprint or accounts you are authorized to investigate. Verify each profile at its source.</p>
  <a class="btn btn-primary" href="/#tool=username">Check a username</a>
  <p class="discovery-note">Free guest previews. Account and plan limits apply. No private-profile access or guaranteed username availability.</p>
  <section><h2>How to search a username across platforms</h2>
  <ol><li>Enter a handle you use or have permission to research in the <a href="/#tool=username">username search tool</a>.</li><li>Run the standard sweep. Try another known spelling separately if you have used different handles.</li><li>Review found, not found and unknown checks. Open reported profile URLs before drawing conclusions.</li><li>For your own accounts, compare the result with signup emails and saved logins. Secure or close accounts through the official service.</li></ol>
  <p>A username lookup searches a handle, not a personal name. Different people can use the same handle on different sites. Read the <a href="/guides/verify-osint-account-matches">account-match verification guide</a> before linking profiles.</p></section>
  <section><h2>Username search vs username availability</h2>
  <p>People searching for a social media username checker often want either existing profile links or a handle they can register. These are different questions. MyRecon supports public profile research. For a brand name or creator handle, check registration directly with each platform.</p>
  <dl><dt><strong>Found</strong></dt><dd>A supported check found evidence of a public profile. Review the source; ownership remains unconfirmed.</dd><dt><strong>Not found</strong></dt><dd>The check did not find the expected public profile. This does not establish registration availability or rule out other handles.</dd><dt><strong>Unknown</strong></dt><dd>The check could not reach a reliable conclusion, for example because of a block, timeout or ambiguous response. Retry or check manually.</dd></dl>
  <p>Reserved names, renamed profiles and suspended accounts can remain unavailable even when a public page is missing. <a href="/guides/why-username-checkers-report-fake-accounts">Learn why username checkers can report false matches</a>.</p></section>
  <section><h2>Platform-specific username lookup guides</h2>
  <p>Platform rules and public visibility differ. Use the relevant guide to understand what can be checked.</p>
  <ul><li><a href="/find/instagram-account">Instagram username lookup</a></li><li><a href="/find/tiktok-profile">TikTok username lookup</a></li><li><a href="/find/github-profile">GitHub profile lookup</a></li><li><a href="/find/reddit-activity">Reddit username lookup</a></li><li><a href="/find/">All platform lookup guides</a></li></ul></section>
  <section><h2>Review your digital footprint</h2><p>Start with usernames you own, record the public profiles you recognize and review what each profile exposes. A username scan is one part of an audit: breach exposure, old accounts and profile visibility need separate checks.</p>
  <ul><li><a href="/blog/find-your-own-old-accounts.html">Find your own old social media accounts</a></li><li><a href="/guides/check-email-data-breach.html">Check whether your email appeared in a data breach</a></li><li><a href="/blog/own-footprint-audit-checklist.html">Use a digital footprint audit checklist</a></li><li><a href="/username-sweep-vs-deep-search.html">Compare a username sweep with Deep Search</a></li><li><a href="/vs/">Compare MyRecon with other OSINT tools</a></li></ul></section>
  <section><h2>Username checker questions</h2><div class="faq">${questions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div><p><a href="/pricing">Current plans and limits</a> · <a href="/privacy.html">Privacy and data handling</a></p></section>
  <section><h2>Evidence and responsible use</h2><p>MyRecon publishes a <a href="/#benchmarks">recorded username comparison</a> with methodology and uncertainty. A single case study does not establish overall accuracy. Use public-source checks for your own accounts and authorized research, following the <a href="/terms.html">terms of use</a>.</p><p>Reviewed for this release: October 1, 2026.</p></section>
</main>`;
let html = fs.readFileSync(path.join(root, 'about.html'), 'utf8');
html = html.replace(/<title>.*?<\/title>/s, `<title>${title.replace(/&/g, '&amp;')}</title>`);
html = html.replace(/(<meta\b[^>]*(?:name="(?:description|twitter:description)"|property="og:description")[^>]*content=")[^"]*/g, `$1${description}`);
html = html.replace(/(<meta\b[^>]*(?:name="twitter:title"|property="og:title")[^>]*content=")[^"]*/g, `$1${title.replace(/&/g, '&amp;')}`);
html = html.replace(/https:\/\/www\.myrecon\.xyz\/about\.html/g, url);
html = html.replace(/<script\b[^>]*type="application\/ld\+json"[^>]*>.*?<\/script>/gs, '');
const graph = { '@context': 'https://schema.org', '@graph': [
  { '@type': 'WebPage', '@id': `${url}#page`, url, name: title, description, dateModified: '2026-10-01', inLanguage: 'en', isPartOf: { '@id': `${site}/#website` }, publisher: { '@id': `${site}/#organization` } },
  { '@type': 'BreadcrumbList', itemListElement: [{ '@type': 'ListItem', position: 1, name: 'MyRecon', item: `${site}/` }, { '@type': 'ListItem', position: 2, name: 'Username checker', item: url }] },
  { '@type': 'FAQPage', mainEntity: questions.map(([name, text]) => ({ '@type': 'Question', name, acceptedAnswer: { '@type': 'Answer', text } })) },
] };
html = html.replace('</head>', `<link rel="stylesheet" href="/assets/css/discovery.css">\n<script type="application/ld+json">${JSON.stringify(graph).replace(/</g, '\\u003c')}</script>\n</head>`);
html = html.replace(/<main\b[^>]*>.*?<\/main>/s, body);
fs.writeFileSync(path.join(root, 'username-checker.html'), html);
console.log('[discovery] Built username-checker.html');
