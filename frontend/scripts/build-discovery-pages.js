/* Keep public discovery and tool landing pages in the production static build. */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const site = 'https://www.myrecon.xyz';

function buildDiscoveryPage({ title, description, keywords, url, outFileName, crumbLabel, questions, bodyHtml, videoObject, modifiedAt = '2026-10-18' }) {
  let html = fs.readFileSync(path.join(root, 'about.html'), 'utf8');
  html = html.replace(/<title>.*?<\/title>/s, `<title>${title.replace(/&/g, '&amp;')}</title>`);
  html = html.replace(/(<meta\b[^>]*(?:name="(?:description|twitter:description)"|property="og:description")[^>]*content=")[^"]*/g, `$1${description}`);
  html = html.replace(/(<meta\b[^>]*(?:name="twitter:title"|property="og:title")[^>]*content=")[^"]*/g, `$1${title.replace(/&/g, '&amp;')}`);
  html = html.replace(/https:\/\/www\.myrecon\.xyz\/about\.html/g, url);
  html = html.replace(/(<meta\b[^>]*name="robots"[^>]*content=")[^"]*/g, '$1index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1');
  html = html.replace(/<script\b[^>]*type="application\/ld\+json"[^>]*>.*?<\/script>/gs, '');

  if (!html.includes('property="og:locale"')) {
    html = html.replace(/(<meta\b[^>]*property="og:site_name"[^>]*>)/, '$1\n  <meta property="og:locale" content="en_US">');
  }

  if (keywords) {
    if (html.includes('name="keywords"')) {
      html = html.replace(/(<meta\b[^>]*name="keywords"[^>]*content=")[^"]*/g, `$1${keywords}`);
    } else {
      html = html.replace(/(<meta\b[^>]*name="description"[^>]*>)/, `$1\n  <meta name="keywords" content="${keywords}">`);
    }
  }

  const graph = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'WebPage',
        '@id': `${url}#page`,
        url,
        name: title,
        description,
        dateModified: modifiedAt,
        inLanguage: 'en',
        isPartOf: { '@id': `${site}/#website` },
        publisher: {
          '@type': 'Organization',
          '@id': `${site}/#organization`,
          name: 'MyRecon',
          url: `${site}/`,
          logo: {
            '@type': 'ImageObject',
            url: `${site}/assets/img/og-image.png`,
            width: 1200,
            height: 630,
          },
        },
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'MyRecon', item: `${site}/` },
          { '@type': 'ListItem', position: 2, name: crumbLabel, item: url },
        ],
      },
      {
        '@type': 'FAQPage',
        mainEntity: questions.map(([name, text]) => ({
          '@type': 'Question',
          name,
          acceptedAnswer: { '@type': 'Answer', text },
        })),
      },
    ],
  };

  html = html.replace('</head>', `<link rel="stylesheet" href="/assets/css/discovery.css">\n<script type="application/ld+json">${JSON.stringify(graph).replace(/</g, '\\u003c')}</script>\n</head>`);
  if (videoObject) {
    graph['@graph'].push(videoObject);
  }
  html = html.replace(/<main\b[^>]*>.*?<\/main>/s, bodyHtml);

  const outPath = path.join(root, outFileName);
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      fs.writeFileSync(outPath, html);
      break;
    } catch (err) {
      if (attempt === 4) throw err;
      const wait = 100 * (attempt + 1);
      const start = Date.now();
      while (Date.now() - start < wait) {}
    }
  }
  console.log(`[discovery] Built ${outFileName}`);
}

// 1. Username checker discovery page
const usernameQuestions = [
  ['What is a username checker?', 'A username checker searches supported services for public profiles using a handle. MyRecon returns profile leads for source review. A matching handle does not prove who owns an account.'],
  ['Can I check username availability with MyRecon?', 'MyRecon checks public profile presence. A not-found result does not guarantee that a username is available to register. A platform may reserve a name, suspend an account or restrict its visibility. Confirm availability in the official signup or account settings flow.'],
  ['Is the username checker free?', 'MyRecon offers free guest Quick scans across 100 platforms with no sign-up required. Only the first 2 result cards are visible; remaining cards are blurred. Standard scans across 500+ platforms require sign-in. Paid plans add features such as Deep Search and Extended scans; check the current pricing page for limits.'],
  ['Can I search every social media platform?', 'No. MyRecon checks a supported catalogue of more than 500 platforms, not every website. Login walls, anti-bot controls, timeouts and platform changes can leave a check unknown.'],
  ['How do I find my old accounts by username?', 'Search handles you remember using, then open each candidate profile and compare it with your own records. Use saved passwords, signup emails and the official account recovery process to confirm ownership.'],
];

const usernameBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Username checker</span></nav>
  <h1>Username checker and social media username search</h1>
  <p class="sub">MyRecon searches a public username across a supported catalogue of 500+ platforms. Use it to review your own digital footprint or accounts you are authorized to investigate. Verify each profile at its source.</p>
  <a class="btn btn-primary" href="/#tool=username">Check a username</a>
  <p class="discovery-note">Free guest Quick scans. Standard scans require sign-in. Account and plan limits apply. No private-profile access or guaranteed username availability.</p>
  <section><h2>How to search a username across platforms</h2>
  <ol><li>Enter a handle you use or have permission to research in the <a href="/#tool=username">username search tool</a>.</li><li>Run the standard sweep. Try another known spelling separately if you have used different handles.</li><li>Review found, not found and unknown checks. Open reported profile URLs before drawing conclusions.</li><li>For your own accounts, compare the result with signup emails and saved logins. Secure or close accounts through the official service.</li></ol>
  <p>A username lookup searches a handle, not a personal name. Different people can use the same handle on different sites. Read the <a href="/guides/verify-osint-account-matches">account-match verification guide</a> before linking profiles.</p></section>
  <section><h2>Social media checker: find accounts by username</h2>
  <p>A social media checker can help you find public profile candidates associated with a handle. Start with your current username, then check older handles individually. This also covers a reverse username lookup: you start with a handle and work back to possible public accounts, without assuming they all belong to one person.</p>
  <p>For example, if you once used <code>sample_handle</code> for gaming and later changed it on social media, check both known handles. Compare links you published yourself, account history you recognize and saved logins. A matching photo or display name alone can be copied.</p>
  <p>For a single network, use the <a href="/find/instagram-account">Instagram OSINT and username lookup guide</a>. For broader cleanup, follow the <a href="/digital-footprint-checker.html">email and username footprint audit</a>.</p></section>
  <section><h2>Username search vs username availability</h2>
  <p>People searching for a social media username checker often want either existing profile links or a handle they can register. These are different questions. MyRecon supports public profile research. For a brand name or creator handle, check registration directly with each platform.</p>
  <dl><dt><strong>Found</strong></dt><dd>A supported check found evidence of a public profile. Review the source; ownership remains unconfirmed.</dd><dt><strong>Not found</strong></dt><dd>The check did not find the expected public profile. This does not establish registration availability or rule out other handles.</dd><dt><strong>Unknown</strong></dt><dd>The check could not reach a reliable conclusion, for example because of a block, timeout or ambiguous response. Retry or check manually.</dd></dl>
  <p>Reserved names, renamed profiles and suspended accounts can remain unavailable even when a public page is missing. <a href="/guides/why-username-checkers-report-fake-accounts.html">Learn why username checkers can report false matches</a>.</p></section>
  <section><h2>Platform-specific username lookup guides</h2>
  <p>Platform rules and public visibility differ. Use the relevant guide to understand what can be checked.</p>
  <ul><li><a href="/find/instagram-account">Instagram username lookup</a></li><li><a href="/find/tiktok-profile">TikTok username lookup</a></li><li><a href="/find/github-profile">GitHub profile lookup</a></li><li><a href="/find/reddit-activity">Reddit username lookup</a></li><li><a href="/find/">All platform lookup guides</a></li></ul></section>
  <section><h2>Review your digital footprint</h2><p>Start with usernames you own, record the public profiles you recognize and review what each profile exposes. A username scan is one part of an audit: breach exposure, old accounts and profile visibility need separate checks.</p>
  <ul><li><a href="/free-osint-tool.html">Free OSINT tool and investigation features</a></li><li><a href="/digital-footprint-checker.html">Digital footprint checker &amp; exposure audit</a></li><li><a href="/reverse-username-lookup.html">Reverse username lookup across 500+ platforms</a></li><li><a href="/boost.html">Boost OSINT investigations &amp; parallel username sweeps</a></li><li><a href="/browser.html">Browser OSINT tool &amp; web username scanner</a></li><li><a href="/goal.html">Digital footprint goal &amp; privacy audit roadmap</a></li><li><a href="/blog/find-your-own-old-accounts.html">Find your own old social media accounts</a></li><li><a href="/guides/check-email-data-breach.html">Check whether your email appeared in a data breach</a></li><li><a href="/services.html">Personal footprint removal service</a></li><li><a href="/blog/own-footprint-audit-checklist.html">Use a digital footprint audit checklist</a></li><li><a href="/username-sweep-vs-deep-search.html">Compare a username sweep with Deep Search</a></li><li><a href="/vs/">Compare MyRecon with other OSINT tools</a></li></ul></section>
  <section><h2>Username checker questions</h2><div class="faq">${usernameQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div><p><a href="/pricing">Current plans and limits</a> · <a href="/privacy.html">Privacy and data handling</a></p></section>
  <section><h2>Evidence and responsible use</h2><p>MyRecon publishes a <a href="/#benchmarks">recorded username comparison</a> with methodology and uncertainty. A single case study does not establish overall accuracy. Use public-source checks for your own accounts and authorized research, following the <a href="/terms.html">terms of use</a>.</p><p>Reviewed for this release: October 20, 2026.</p></section>
</main>`;

buildDiscoveryPage({
  title: 'Username Lookup & Social Media Username Checker | MyRecon',
  description: 'Check public usernames across 500+ platforms with MyRecon. Review social media profile leads, unknown results and username availability limits.',
  keywords: 'username checker, social media username search, username lookup, check username across platforms, find accounts by username, public profile search, handle checker, username availability vs search, browser username checker, osint username search',
  url: `${site}/username-checker.html`,
  outFileName: 'username-checker.html',
  crumbLabel: 'Username checker',
  questions: usernameQuestions,
  bodyHtml: usernameBody,
  modifiedAt: '2026-10-20',
});

// 2. Free OSINT tool discovery page
const osintQuestions = [
  ['What is a free OSINT tool?', 'An OSINT (Open-Source Intelligence) tool collects and analyzes information from publicly accessible online sources, such as social platforms, developer profiles, breach repositories, domain registrations, and DNS records. MyRecon provides a free browser-based OSINT scanner to map your digital footprint or conduct authorized security investigations without installing software.'],
  ['Is MyRecon really free to use for OSINT investigations?', 'Yes. MyRecon provides free guest Quick scans across 100 platforms with zero setup or sign-in required. Users with an account can run Standard scans across 500+ platforms, query email breach exposure, check password exposure via k-anonymity, and audit domain DNS configurations at no cost. Paid plans add Deep Search and Extended 3,000+ platform sweeps.'],
  ['How does MyRecon compare to CLI tools like Sherlock and Maigret?', 'Command-line tools like Sherlock and Maigret require Python environments, Git, and package management, running requests from your terminal IP. MyRecon runs directly in your web browser or Android app with zero installation. Additionally, MyRecon tests against synthetic control handles to eliminate false-positive 200 OK responses and integrates email breach and DNS intelligence in a unified dashboard.'],
  ['Can a free OSINT tool find private or hidden social accounts?', 'No. Legitimate OSINT tools only query publicly accessible endpoints, indexed profiles, and public registries. They do not bypass passwords, exploit vulnerabilities, or intercept private communications. If a profile is restricted, suspended, or behind a login wall, MyRecon transparently reports the result as unknown rather than assuming it is absent.'],
  ['What investigation modules are included in MyRecon\'s free OSINT suite?', 'MyRecon includes reverse username search across 500+ platforms, email breach detection against billions of compromised records, password leak checking using k-anonymity SHA-1 prefixes, domain WHOIS and RDAP registration lookup, and DNS mail-authentication checks for SPF and DMARC spoofing defense.'],
];

const osintBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Free OSINT tool</span></nav>
  <h1>Free OSINT tool and online investigation platform</h1>
  <p class="sub">MyRecon is a browser-based Open-Source Intelligence (OSINT) platform for reverse username search, digital footprint audits, email breach detection, and domain intelligence across 500+ sources. Search instantly with zero installation.</p>
  <a class="btn btn-primary" href="/#tool">Start free OSINT investigation</a>
  <p class="discovery-note">Zero setup required. Free guest Quick scans across 100 platforms. Standard scans cover 500+ platforms. Ethical public-source research only.</p>
  <section>
    <h2>What is an OSINT tool and how does it work?</h2>
    <p>Open-Source Intelligence (OSINT) refers to intelligence derived from publicly accessible data. A free OSINT tool automates the collection and correlation of public data across social networks, developer hubs, public registries, and breached credential archives.</p>
    <p>Instead of manually visiting hundreds of websites, MyRecon queries public profile endpoints simultaneously. To prevent misleading results, MyRecon evaluates HTTP responses against synthetic control handles, classifying every check into three precise evidence states:</p>
    <dl>
      <dt><strong>Found</strong></dt>
      <dd>A supported public endpoint returned confirmed evidence of a public profile. The candidate link should be reviewed at the source to confirm ownership.</dd>
      <dt><strong>Not found</strong></dt>
      <dd>The public check completed without finding a public profile. This indicates absence on the tested endpoint, though accounts under alternate aliases or restricted settings may exist.</dd>
      <dt><strong>Unknown</strong></dt>
      <dd>The target platform returned a block, rate limit, anti-bot challenge, or ambiguous response. MyRecon never invents answers; unresolved checks remain transparently unknown.</dd>
    </dl>
  </section>
  <section>
    <h2>Core OSINT investigation modules</h2>
    <p>MyRecon integrates multiple reconnaissance capabilities into a single unified workspace:</p>
    <ol>
      <li><strong>Reverse username lookup:</strong> Sweep handles across 500+ platforms, including Instagram, GitHub, TikTok, Reddit, X (Twitter), Discord, and YouTube. Read our <a href="/username-checker.html">username checker guide</a> and <a href="/reverse-username-lookup.html">reverse username search overview</a>.</li>
      <li><strong>Email breach intelligence:</strong> Verify whether an email address has surfaced in historical corporate leaks or data breaches. Read our <a href="/guides/check-email-data-breach.html">breach checking guide</a>.</li>
      <li><strong>Password exposure audits:</strong> Check password status using k-anonymity SHA-1 prefixes, ensuring credentials are never transmitted over the network in plaintext.</li>
      <li><strong>Domain &amp; DNS security checks:</strong> Query domain RDAP/WHOIS registrations and verify SPF, DKIM, and DMARC configurations to detect email spoofing risks.</li>
      <li><strong>IP geolocation and infrastructure recon:</strong> Resolve network hostnames, autonomous system numbers (ASNs), and reverse DNS records.</li>
    </ol>
  </section>
  <section>
    <h2>How to conduct a free OSINT investigation</h2>
    <ol>
      <li>Enter a target username, email address, or domain into the <a href="/#tool">MyRecon OSINT scanner</a>.</li>
      <li>Run the public sweep across your chosen scope (Quick, Standard, or Extended).</li>
      <li>Review the evidence-backed results and note profile links, breach exposures, and network configuration findings.</li>
      <li>Cross-verify critical leads using our <a href="/guides/what-is-osint.html">OSINT workflow guide</a> and record timestamps for evidence integrity.</li>
    </ol>
  </section>
  <section>
    <h2>Comparing free OSINT tools: Web scanner vs CLI scripts</h2>
    <p>Traditional open-source intelligence tools like Sherlock, Maigret, and WhatsMyName are built as command-line terminal scripts. While powerful for developers, they present operational friction:</p>
    <ul>
      <li><strong>Installation overhead:</strong> CLI tools require Python, pip package dependencies, and terminal environments. MyRecon runs instantly in any modern browser on desktop or mobile.</li>
      <li><strong>Rate limiting and IP burning:</strong> Running high-speed terminal sweeps from a personal home IP often triggers CAPTCHAs and temporary IP bans. MyRecon balances query distribution to maintain reliability.</li>
      <li><strong>False-positive elimination:</strong> Many platforms return HTTP 200 responses for nonexistent accounts. MyRecon validates responses against impossible control handles to filter out ghost accounts.</li>
      <li><strong>Integrated intelligence:</strong> CLI tools typically focus only on usernames. MyRecon combines usernames, email breaches, password exposure, and domain DNS analysis in one view.</li>
    </ul>
    <p>See our head-to-head technical comparisons: <a href="/vs/sherlock.html">MyRecon vs Sherlock</a>, <a href="/vs/maigret.html">MyRecon vs Maigret</a>, and <a href="/vs/">all OSINT tool comparisons</a>.</p>
  </section>
  <section>
    <h2>Featured OSINT resources and tools</h2>
    <p>Explore our research library, cheat sheets, and specialized investigation workflows:</p>
    <ul>
      <li><a href="/digital-footprint-checker.html">Digital footprint checker &amp; exposure audit</a></li>
      <li><a href="/reverse-username-lookup.html">Reverse username lookup across 500+ platforms</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
      <li><a href="/boost.html">Boost OSINT investigations &amp; high-speed sweeps</a></li>
      <li><a href="/browser.html">Browser OSINT tool &amp; web username scanner</a></li>
      <li><a href="/goal.html">Digital footprint goal &amp; privacy audit roadmap</a></li>
      <li><a href="/osint-cheat-sheet.html">OSINT cheat sheet &amp; Google dork generator</a></li>
      <li><a href="/deep-search.html">Deep Search: public activity &amp; mentions</a></li>
      <li><a href="/blog/best-free-osint-tools-for-investigators.html">Best free OSINT tools for researchers in 2026</a></li>
      <li><a href="/blog/best-osint-tools-username-search-comparison.html">Top 8 OSINT username tools compared</a></li>
      <li><a href="/guides/build-a-breach-monitor.html">How to build a personal data breach monitor</a></li>
      <li><a href="/guides/photo-metadata-exif.html">EXIF and photo metadata investigation guide</a></li>
      <li><a href="/guides/read-an-email-header.html">How to read and analyze email headers for spoofing</a></li>
      <li><a href="/services.html">Personal digital footprint removal service</a></li>
      <li><a href="/pricing.html">Plans and scan limits</a></li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions about free OSINT tools</h2>
    <div class="faq">${osintQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Ethical OSINT research and guidelines</h2>
    <p>Open-source intelligence is a defensive discipline for security auditing, brand protection, and personal privacy. MyRecon only inspects publicly available web endpoints. Never use intelligence tools for harassment, unauthorized stalking, or illegal access. Read our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Reviewed for this release: October 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Free OSINT Tool & Online Investigation Platform | MyRecon',
  description: 'Free OSINT tool to search usernames across 500+ platforms, check email breach exposure, and audit digital footprints. Start your free investigation online.',
  keywords: 'free osint tool, free osint tools, free osint search, open source intelligence tool, osint tools online, browser osint tool, web browser osint scanner, boost osint investigation, best free osint tools, free reverse username lookup, free digital footprint checker, social media osint tool, email osint tool, online osint investigation, cyber reconnaissance, sherlock alternative free, find accounts by username free, search username across platforms',
  url: `${site}/free-osint-tool.html`,
  outFileName: 'free-osint-tool.html',
  crumbLabel: 'Free OSINT tool',
  questions: osintQuestions,
  bodyHtml: osintBody,
});

// 3. Digital footprint checker discovery page
const footprintQuestions = [
  ['Can I check my digital footprint by email?', 'An email breach check can identify exposure in supported breach sources. It does not list every account registered to an address or prove that an account is currently active. Combine it with your own signup emails, saved passwords and username checks.'],
  ['Can I completely clear my digital footprint?', 'You can reduce public exposure by deleting accounts, removing published details and requesting eligible removals. You cannot guarantee complete erasure of backups, archived copies or third-party records. Verify each removal at its source and check again later.'],
  ['What is a digital footprint checker?', 'A digital footprint checker is an OSINT security tool that audits the public trail of data you leave behind on the internet. It scans for registered usernames across social platforms, checks whether your email address has appeared in data breaches, reviews leaked credentials, and analyzes public DNS records.'],
  ['How do I check my digital footprint for free?', 'Choose a username check for public profile leads or an email check for supported breach exposure. Free guest Quick username scans cover 100 platforms with limited visible results; Standard scans require sign-in. Review current plan limits and verify each result at its source.'],
  ['What is the difference between active and passive digital footprints?', 'An active digital footprint consists of data you intentionally post online, such as social media posts, public profiles, and forum discussions. A passive digital footprint includes data collected about you without your direct action, such as data broker listings, breach corpora, and server logs. MyRecon helps audit both public profiles and historical breach leaks.'],
  ['How can I clean up or reduce my digital footprint?', 'Start by reviewing public profile leads and supported email breach results with MyRecon, then confirm your own accounts using saved logins and signup messages. Delete dormant accounts, request opt-outs from people-search data brokers, enable two-factor authentication on critical services, and replace breached passwords. Follow our digital footprint reduction guide for step-by-step instructions.'],
  ['Does a digital footprint check affect my credit score or alert anyone?', 'MyRecon checks supported public sources and breach data; it is not a credit check. Requests can be logged by source services, so do not assume research is invisible. It does not grant access to private accounts.'],
];

const footprintBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Digital footprint checker</span></nav>
  <h1>Free digital footprint checker and online exposure audit</h1>
  <p class="sub">Audit your public online exposure with MyRecon's free digital footprint scanner. Search usernames across 500+ platforms, review supported email breach exposure, and plan your cleanup.</p>
  <a class="btn btn-primary" href="/#tool">Check your digital footprint</a>
  <p class="discovery-note">Zero installation. Free guest Quick scans across 100 platforms. Standard scans cover 500+ platforms. Ethical public-source research only.</p>
  <section>
    <h2>What is a digital footprint and why should you audit it?</h2>
    <p>Every time you sign up for a web service, post on social media, register a domain, or submit your email address, you leave behind digital traces. Over time, these traces accumulate into a substantial digital footprint. Dormant accounts, old forum handles, and forgotten registrations create an attack surface for credential stuffing, impersonation, and identity theft.</p>
    <p>A digital footprint audit allows you to catalog your active public footprint, identify which accounts are still accessible, and discover where your personal data has been exposed through third-party data breaches.</p>
  </section>
  <section>
    <h2>How to conduct a free digital footprint check</h2>
    <ol>
      <li><strong>Gather your identifiers:</strong> List the primary handles, legacy screen names, and personal or work email addresses you have used over the years.</li>
      <li><strong>Scan usernames across 500+ platforms:</strong> Enter your handle into the <a href="/#tool=username">MyRecon username scanner</a> to see where public profiles are found.</li>
      <li><strong>Audit email breach exposure:</strong> Enter your email address to check against historical corporate breaches and security compromises. Read our <a href="/guides/check-email-data-breach.html">breach checking guide</a>.</li>
      <li><strong>Inspect password leaks:</strong> Verify whether any reused passwords have surfaced in credential dumps using our zero-knowledge k-anonymity checker.</li>
      <li><strong>Review domain and DNS exposure:</strong> If you own a personal domain or website, check WHOIS records and email spoofing defenses (SPF, DMARC) via the <a href="/#tool=domain">domain lookup tool</a>.</li>
    </ol>
  </section>
  <section>
    <h2>Core components of MyRecon's digital footprint checker</h2>
    <dl>
      <dt><strong>Reverse username enumeration</strong></dt>
      <dd>Simultaneously inspect 500+ social networks, developer hubs, gaming communities, and streaming services. MyRecon uses synthetic controls to help reduce false positives; source review is still necessary.</dd>
      <dt><strong>Data breach intelligence</strong></dt>
      <dd>Query billions of compromised records from verified historical data breaches to identify compromised accounts and leaked personal data fields.</dd>
      <dt><strong>Credential exposure checks</strong></dt>
      <dd>Evaluate password hygiene safely using SHA-1 hash prefixes. Your plaintext password never leaves your browser.</dd>
      <dt><strong>Infrastructure and domain recon</strong></dt>
      <dd>Analyze domain registration data, IP geolocation, ASN infrastructure, and mail security records to identify exposed assets.</dd>
    </dl>
  </section>
  <section>
    <h2>Digital footprint checker by email: what it can tell you</h2>
    <p>Use the <a href="/#tool=email">email breach checker</a> for an address you control. Review the reported breach name, affected data categories and source context. A historical breach result is different from a currently accessible account, and an empty result does not establish that the address has never been exposed.</p>
    <p>To find accounts linked to your own email, review saved passwords and search your inbox for welcome, verification and subscription messages. Open the official service directly before recovering an account. An email address alone cannot reveal every social profile or private registration.</p>
    <p>Use the <a href="/guides/username-search-vs-email-search">username search vs email search guide</a> to choose the right check. Never paste passwords into a username or email field.</p>
  </section>
  <section>
    <h2>How to clear your digital footprint: a practical cleanup order</h2>
    <p>Start with accounts you can verify as yours. Record the source URL, the exposed detail, the action requested and a recheck date. Remove information at the source first; a search-result removal does not delete the original page. Follow the <a href="/guides/reduce-your-digital-footprint.html">step-by-step digital footprint cleanup guide</a>.</p>
    <p>Once you have identified your public exposure, take proactive steps to reduce risk:</p>
    <ul>
      <li><strong>Close dormant accounts:</strong> Visit old accounts discovered during your scan, export any personal data you wish to keep, and permanently delete the accounts. Read our guide on <a href="/blog/find-your-own-old-accounts.html">finding your old accounts</a>.</li>
      <li><strong>Remove personal information from data brokers:</strong> Many people-search sites scrape public records. Request removal using our <a href="/privacy/">data broker removal guides</a>.</li>
      <li><strong>Update compromised credentials:</strong> If an email or password appeared in breach corpora, immediately change passwords on all associated accounts and enable multi-factor authentication (MFA).</li>
      <li><strong>Reduce social media visibility:</strong> Adjust privacy settings on active profiles to limit what public search engines and strangers can view. See our <a href="/guides/reduce-your-digital-footprint.html">footprint reduction checklist</a>.</li>
    </ul>
  </section>
  <section>
    <h2>Featured digital footprint and OSINT resources</h2>
    <ul>
      <li><a href="/free-osint-tool.html">Free OSINT tool and online investigation platform</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
      <li><a href="/reverse-username-lookup.html">Reverse username lookup across 500+ platforms</a></li>
      <li><a href="/goal.html">Digital footprint goal &amp; privacy audit roadmap</a></li>
      <li><a href="/boost.html">Boost OSINT investigations &amp; parallel sweeps</a></li>
      <li><a href="/browser.html">Browser OSINT tool &amp; web username scanner</a></li>
      <li><a href="/osint-cheat-sheet.html">OSINT cheat sheet &amp; Google dork generator</a></li>
      <li><a href="/blog/digital-footprint-checker-guide.html">Digital footprint checker guide (2026)</a></li>
      <li><a href="/guides/build-a-breach-monitor.html">Build a personal data breach monitor</a></li>
      <li><a href="/guides/photo-metadata-exif.html">Inspect EXIF and photo metadata exposure</a></li>
      <li><a href="/guides/read-an-email-header.html">Read email headers to verify sender authenticity</a></li>
      <li><a href="/services.html">Personal footprint removal service</a></li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions</h2>
    <div class="faq">${footprintQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Ethical and responsible use</h2>
    <p>MyRecon provides digital footprint auditing tools strictly for personal privacy reviews and authorized security research. We only query public endpoints and transparently distinguish found, not found, and unknown states. Review our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Reviewed for this release: October 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Digital Footprint Checker by Email & Username | MyRecon',
  description: 'Check public username profiles and email breach exposure. Learn what each result means and follow practical steps to reduce your digital footprint.',
  keywords: 'digital footprint checker, free digital footprint checker, digital footprint search, digital footprint audit, check digital footprint free, online footprint audit, how to check digital footprint, digital footprint scanner, reverse digital footprint, personal privacy audit, privacy goal checklist, digital footprint cleanup goal, zero footprint goal, check online exposure free, search digital footprint by name',
  url: `${site}/digital-footprint-checker.html`,
  outFileName: 'digital-footprint-checker.html',
  crumbLabel: 'Digital footprint checker',
  questions: footprintQuestions,
  bodyHtml: footprintBody,
  modifiedAt: '2026-10-20',
});

// 4. Reverse username lookup discovery page
const lookupQuestions = [
  ['What is a reverse username lookup?', 'A reverse username lookup is an OSINT reconnaissance technique that takes a single username or handle and queries hundreds of web platforms to identify registered public profiles associated with that handle.'],
  ['Is reverse username lookup free on MyRecon?', 'Yes. MyRecon allows anyone to run free guest Quick scans across 100 platforms with no login required. Creating a free account unlocks Standard scans across 500+ platforms with complete result cards, exportable summaries, and saved search history.'],
  ['How does reverse username search differ from searching Google?', 'Traditional search engines only index pages that have been discovered and crawled, often missing new profiles, profile changes, and niche platforms. A reverse username lookup queries the platform\'s public URL endpoint directly in real time, detecting accounts even if Google has not indexed them.'],
  ['How does MyRecon prevent false positives during username searches?', 'Many social networks return HTTP 200 OK status codes for non-existent users (soft 404s). MyRecon tests every platform against a synthetic control handle alongside the target handle. If a site responds identically for both, the result is flagged to prevent false-positive matches.'],
  ['Can a reverse username search prove who owns an account?', 'No. A matching username is an investigative lead, not conclusive proof of identity. Different people can independently choose the same handle on different websites. Always verify account ownership by reviewing profile content, joined dates, and cross-linked social profiles.'],
];

const lookupBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Reverse username lookup</span></nav>
  <h1>Free reverse username lookup &amp; social media account search</h1>
  <p class="sub">Query handles across 500+ social platforms, developer hubs, and forums simultaneously. Discover profile leads, eliminate false positives with synthetic control tests, and map online accounts instantly.</p>
  <a class="btn btn-primary" href="/#tool=username">Start reverse username lookup</a>
  <p class="discovery-note">No terminal setup required. Free guest Quick scans across 100 platforms. Standard scans cover 500+ platforms. Public evidence research only.</p>
  <section>
    <h2>What is reverse username lookup and how does it work?</h2>
    <p>A reverse username search takes a known handle, alias, or screen name and probes hundreds of online services to find matching public profiles. Because people frequently reuse the same username across different websites, a reverse lookup connects fragmented profiles into a unified digital footprint.</p>
    <p>Instead of manual searching or maintaining complex command-line scripts, MyRecon runs browser-based multi-threaded queries against 500+ platforms including Instagram, GitHub, Reddit, TikTok, X (Twitter), YouTube, Discord, and Telegram.</p>
  </section>
  <section>
    <h2>How to perform an effective reverse username search</h2>
    <ol>
      <li><strong>Enter the target username:</strong> Input the exact handle into the <a href="/#tool=username">reverse username tool</a>.</li>
      <li><strong>Choose your scan scope:</strong> Start with a Quick scan (100 top platforms) or sign in for a Standard scan covering 500+ platforms.</li>
      <li><strong>Evaluate evidence-backed states:</strong> Review results categorized as found, not found, or unknown. MyRecon never guesses; if a site rate-limits or blocks a query, it remains unknown.</li>
      <li><strong>Verify leads at the source:</strong> Click the reported profile URLs to confirm account activity, creation dates, and public profile bios. Read our guide on <a href="/guides/verify-osint-account-matches.html">verifying OSINT account matches</a>.</li>
    </ol>
  </section>
  <section>
    <h2>Overcoming false positives: The synthetic control advantage</h2>
    <p>One major flaw in traditional CLI username tools like Sherlock and Maigret is susceptibility to soft 404s. Many modern web applications return an HTTP 200 OK status code with a "user not found" splash screen or redirect to a landing page, causing terminal tools to report ghost accounts.</p>
    <p>MyRecon solves this by comparing every query against an impossible synthetic control handle. If a platform returns identical responses for both a real user and a non-existent control handle, MyRecon flags the response rather than falsely claiming an account was found. Read our research on <a href="/guides/why-username-checkers-report-fake-accounts.html">why username checkers report fake accounts</a>.</p>
  </section>
  <section>
    <h2>Related OSINT investigation tools</h2>
    <ul>
      <li><a href="/free-osint-tool.html">Free OSINT tool and online investigation platform</a></li>
      <li><a href="/digital-footprint-checker.html">Free digital footprint checker and online audit</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
      <li><a href="/boost.html">Boost OSINT investigations &amp; high-speed sweeps</a></li>
      <li><a href="/browser.html">Browser OSINT tool &amp; web username scanner</a></li>
      <li><a href="/goal.html">Digital footprint goal &amp; privacy audit roadmap</a></li>
      <li><a href="/deep-search.html">Deep Search: public comments and mentions</a></li>
      <li><a href="/blog/reverse-username-lookup-guide.html">Complete reverse username lookup guide (2026)</a></li>
      <li><a href="/blog/best-osint-tools-username-search-comparison.html">Top 8 OSINT username tools compared</a></li>
      <li><a href="/vs/sherlock.html">MyRecon vs Sherlock comparison</a></li>
      <li><a href="/vs/maigret.html">MyRecon vs Maigret comparison</a></li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions</h2>
    <div class="faq">${lookupQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Ethical investigation guidelines</h2>
    <p>Reverse username lookups must be conducted responsibly. MyRecon queries publicly accessible endpoints and does not bypass private account settings or access restricted data. Use this tool for personal privacy audits, self-reconnaissance, and authorized security assessments. See our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Reviewed for this release: October 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Reverse Username Lookup & Social Media Search | MyRecon',
  description: 'Free reverse username lookup to search handles across 500+ social media networks, forums, and developer sites. Check accounts with zero installation.',
  keywords: 'reverse username lookup, reverse username search, reverse username search free, free reverse username lookup, social media username search, find accounts by username, username lookup, reverse social media lookup, browser reverse username lookup, sherlock online alternative, maigret alternative online, search username across social media, find someone by username',
  url: `${site}/reverse-username-lookup.html`,
  outFileName: 'reverse-username-lookup.html',
  crumbLabel: 'Reverse username lookup',
  questions: lookupQuestions,
  bodyHtml: lookupBody,
});

// 5. Boost OSINT investigations landing page (/boost.html)
const boostQuestions = [
  ['How does MyRecon boost OSINT investigation speed?', 'MyRecon replaces sequential manual checks and fragile terminal scripts with parallelized, multi-vector public queries. In one workspace, you can sweep a username across 500+ platforms, check email breach exposure, verify k-anonymity password status, and inspect domain DNS security records without switching tools.'],
  ['Why do standard username scanners produce slow or noisy results?', 'Many command-line scanners query sites without synthetic control validation, returning dozens of false-positive HTTP 200 responses that an analyst must manually inspect and discard. MyRecon filters out soft-404 ghost accounts automatically so you only spend time reviewing genuine public profile leads.'],
  ['What is the difference between Quick, Standard, and Extended sweeps?', 'Guest Quick scans check 100 major platforms with zero sign-up. Standard scans check 500+ platforms for signed-in users. Extended sweeps and Deep Search add broader platform coverage and public mention correlation for deeper authorized investigations.'],
  ['Does boosting scan speed trigger IP blocks on my home network?', 'When you run CLI tools like Sherlock or Maigret locally, hundreds of rapid requests originate directly from your personal IP address, frequently triggering rate limits and CAPTCHAs. MyRecon orchestrates checks through its cloud scanner infrastructure so your local network is not burned.'],
  ['Can I combine username sweeps with Deep Search and breach checks?', 'Yes. After running a high-speed username sweep, you can pivot directly into Deep Search to inspect indexed public activity, or run an email breach and domain RDAP check from the same console.'],
];

const boostBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Boost OSINT</span></nav>
  <h1>Boost OSINT investigations and parallel username search</h1>
  <p class="sub">Accelerate open-source intelligence workflows with MyRecon. Run parallel username sweeps across 500+ platforms, eliminate soft-404 false positives with synthetic control checks, and correlate email breaches in seconds.</p>
  <a class="btn btn-primary" href="/#tool=username">Boost your OSINT scan</a>
  <p class="discovery-note">Parallel multi-platform sweeps. Synthetic control validation. Free guest Quick scans across 100 platforms; 500+ platforms with free sign-in.</p>
  <section>
    <h2>How to boost OSINT speed without sacrificing accuracy</h2>
    <p>In open-source intelligence, raw request speed means very little if half of the returned URLs are false positives. Traditional username enumeration scripts race through hundreds of URLs and flag any HTTP 200 response as a match, forcing investigators to waste time clicking dead landing pages.</p>
    <p>MyRecon boosts real investigative throughput by combining parallel cloud execution with automated evidence verification:</p>
    <dl>
      <dt><strong>Parallel multi-platform probing</strong></dt>
      <dd>Query 100 to 500+ social networks, coding repositories, gaming networks, and community forums in a single pass instead of checking sites one by one.</dd>
      <dt><strong>Synthetic control filtering</strong></dt>
      <dd>Every target check is paired against a known non-existent control handle so soft 404s and login-wall redirects are caught before they clutter your report.</dd>
      <dt><strong>Three-state evidence classification</strong></dt>
      <dd>Results are separated cleanly into <em>Found</em>, <em>Not found</em>, and <em>Unknown</em> (rate-limited or blocked), preventing false assumptions when a site throttles requests.</dd>
    </dl>
  </section>
  <section>
    <h2>4-step workflow to accelerate your reconnaissance</h2>
    <ol>
      <li><strong>Launch a parallel username sweep:</strong> Enter a handle in the <a href="/#tool=username">MyRecon scanner</a> to probe public profiles across social and developer platforms.</li>
      <li><strong>Pivot to Deep Search mentions:</strong> Use <a href="/deep-search.html">Deep Search</a> to uncover public forum threads, comments, and web mentions tied to the handle.</li>
      <li><strong>Correlate email breach history:</strong> Check whether associated email addresses appear in verified breach corpora using the <a href="/guides/check-email-data-breach.html">email breach workflow</a>.</li>
      <li><strong>Validate domain and DNS posture:</strong> Inspect WHOIS/RDAP records, IP geolocation, and SPF/DMARC policies via the <a href="/#tool=domain">domain intelligence module</a>.</li>
    </ol>
  </section>
  <section>
    <h2>Why investigators switch from CLI scripts to MyRecon</h2>
    <ul>
      <li><strong>Zero environment maintenance:</strong> No Python virtual environments, broken pip dependencies, or outdated JSON site definitions to patch before starting urgent research.</li>
      <li><strong>Protected local IP reputation:</strong> Avoid triggering Cloudflare blocks or CAPTCHA loops on your personal connection during large sweeps.</li>
      <li><strong>Documented benchmark transparency:</strong> Review our <a href="/#benchmarks">published benchmark comparisons</a> against <a href="/vs/sherlock.html">Sherlock</a>, <a href="/vs/maigret.html">Maigret</a>, and <a href="/vs/whatsmyname.html">WhatsMyName</a>.</li>
    </ul>
  </section>
  <section>
    <h2>Related OSINT tools and investigation hubs</h2>
    <ul>
      <li><a href="/free-osint-tool.html">Free OSINT tool and online investigation platform</a></li>
      <li><a href="/browser.html">Browser OSINT tool and web username scanner</a></li>
      <li><a href="/goal.html">Digital footprint goal and privacy audit roadmap</a></li>
      <li><a href="/digital-footprint-checker.html">Free digital footprint checker and exposure audit</a></li>
      <li><a href="/reverse-username-lookup.html">Reverse username lookup across 500+ platforms</a></li>
      <li><a href="/username-checker.html">Username checker and social media search</a></li>
      <li><a href="/osint-cheat-sheet.html">OSINT cheat sheet and search operator builder</a></li>
      <li><a href="/guides/verify-osint-account-matches.html">How to verify OSINT account matches</a></li>
      <li><a href="/guides/why-username-checkers-report-fake-accounts.html">Why username checkers report fake accounts</a></li>
      <li><a href="/pricing.html">MyRecon plans and scan tiers</a></li>
      <li><a href="/services.html">Personal footprint removal service</a></li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions about boosting OSINT workflows</h2>
    <div class="faq">${boostQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Authorized and ethical reconnaissance</h2>
    <p>MyRecon is built for personal footprint self-audits, defensive security teams, and authorized investigations. Only query identifiers you own or have lawful authorization to review. See our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Reviewed for this release: October 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Boost OSINT Investigations & Username Speed | MyRecon',
  description: 'Boost your OSINT investigations with MyRecon. Run parallel username sweeps across 500+ platforms, check email breaches, and verify results with zero CLI setup.',
  keywords: 'boost osint, free osint tool boost, boost osint investigation, boost username search, fast osint scanner, online osint boost, reverse username lookup boost, parallel username search, high speed osint tool, automated osint workflow',
  url: `${site}/boost.html`,
  outFileName: 'boost.html',
  crumbLabel: 'Boost OSINT',
  questions: boostQuestions,
  bodyHtml: boostBody,
});

// 6. Browser OSINT tool landing page (/browser.html)
const browserQuestions = [
  ['What is a browser OSINT tool?', 'A browser OSINT tool is a web-based open-source intelligence platform that runs directly in your browser on desktop or mobile without requiring command-line scripts, Python packages, or local software installation.'],
  ['Can I run a full 500+ platform username scan in my web browser?', 'Yes. MyRecon executes multi-platform username sweeps, email breach checks, password k-anonymity lookups, and domain DNS/WHOIS queries directly from any modern web browser.'],
  ['How does a browser OSINT scanner protect my password during leak checks?', 'MyRecon uses client-side SHA-1 hashing and k-anonymity in your browser. Only the first 5 characters of the SHA-1 hash are sent to the API, and the returned suffix list is compared locally in your browser so your full password never leaves your device.'],
  ['How does MyRecon compare to browser extensions or CLI tools?', 'Browser extensions require broad site permissions and can fingerprint your browsing activity, while CLI tools like Sherlock require terminal setup. MyRecon works in a standard browser tab with zero permissions or installation, and also offers a dedicated Android app.'],
  ['Does the browser OSINT scanner work on mobile phones and tablets?', 'Yes. The MyRecon web console is fully responsive on iOS, Android, macOS, Windows, and Linux browsers, and Android users can also use the native MyRecon Android app.'],
];

const browserBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Browser OSINT tool</span></nav>
  <h1>Browser OSINT tool and web username scanner</h1>
  <p class="sub">Run open-source intelligence investigations directly in your web browser with zero CLI setup. Sweep usernames across 500+ platforms, check email breaches, and audit DNS security from any device.</p>
  <a class="btn btn-primary" href="/#tool">Open browser OSINT scanner</a>
  <p class="discovery-note">No Python, Git, or browser extensions required. Works in any modern desktop or mobile browser. Ethical public-source research only.</p>
  <section>
    <h2>Why use a browser-based OSINT platform?</h2>
    <p>Most open-source username scanners were designed as terminal utilities that require Python runtimes, command-line flags, and manual JSON maintenance. When you need to check a handle or verify a breach quickly on a laptop, tablet, or phone, setting up a local CLI environment slows you down.</p>
    <p>MyRecon delivers a complete reconnaissance console in the browser while preserving rigorous evidence standards:</p>
    <dl>
      <dt><strong>Instant zero-install execution</strong></dt>
      <dd>Open the web console and run username, email, password, IP, or domain checks immediately without installing packages or browser add-ons.</dd>
      <dt><strong>Client-side k-anonymity privacy</strong></dt>
      <dd>Password exposure checks hash your input locally in the browser via the Web Crypto API and transmit only a 5-character SHA-1 prefix.</dd>
      <dt><strong>Cross-device workspace</strong></dt>
      <dd>Switch seamlessly between desktop browsers, mobile browsers, and the <a href="/app.html">MyRecon Android app</a>.</dd>
    </dl>
  </section>
  <section>
    <h2>What you can investigate in the MyRecon browser console</h2>
    <ol>
      <li><strong>Public username enumeration:</strong> Check handles across 500+ social, developer, creator, and forum platforms with <a href="/reverse-username-lookup.html">reverse username lookup</a>.</li>
      <li><strong>Deep Search web correlation:</strong> Surface public posts, profile references, and cross-platform links with <a href="/deep-search.html">Deep Search</a>.</li>
      <li><strong>Email breach and exposure review:</strong> Audit whether an email address appears in public breach records and review <a href="/breaches/">historical breach analyses</a>.</li>
      <li><strong>Domain, WHOIS, and mail security:</strong> Inspect RDAP registration data, SPF, DKIM, and DMARC policies, and IP geolocation from the browser.</li>
      <li><strong>Search operator generation:</strong> Build targeted Google, GitHub, and Reddit queries using the interactive <a href="/osint-cheat-sheet.html">OSINT cheat sheet</a>.</li>
    </ol>
  </section>
  <section>
    <h2>Browser OSINT scanner vs terminal CLI tools</h2>
    <p>Compare how a browser-native workflow stacks up against traditional terminal scripts:</p>
    <ul>
      <li><strong>MyRecon vs Sherlock:</strong> Read our <a href="/vs/sherlock.html">Sherlock comparison</a> to see how browser-based synthetic control checks prevent false positives.</li>
      <li><strong>MyRecon vs Maigret:</strong> Read our <a href="/vs/maigret.html">Maigret comparison</a> for speed, false-positive filtering, and multi-tool integration.</li>
      <li><strong>MyRecon vs WhatsMyName:</strong> Read our <a href="/vs/whatsmyname.html">WhatsMyName comparison</a> and explore <a href="/vs/">all OSINT tool comparisons</a>.</li>
    </ul>
  </section>
  <section>
    <h2>Explore connected MyRecon tools and guides</h2>
    <ul>
      <li><a href="/free-osint-tool.html">Free OSINT tool and online investigation platform</a></li>
      <li><a href="/boost.html">Boost OSINT investigations and parallel sweeps</a></li>
      <li><a href="/goal.html">Digital footprint goal and privacy audit roadmap</a></li>
      <li><a href="/digital-footprint-checker.html">Free digital footprint checker and exposure audit</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
      <li><a href="/reverse-username-lookup.html">Reverse username lookup across 500+ platforms</a></li>
      <li><a href="/guides/what-is-osint.html">What is OSINT? Beginner guide to open-source intelligence</a></li>
      <li><a href="/blog/best-osint-tools-username-search-comparison.html">Best OSINT username search tools compared</a></li>
      <li><a href="/pricing.html">Plans and scan limits</a></li>
      <li><a href="/services.html">Personal footprint removal service</a></li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions about browser OSINT tools</h2>
    <div class="faq">${browserQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Privacy and responsible browser reconnaissance</h2>
    <p>MyRecon queries only public endpoints and never installs background tracking extensions. Use the browser scanner for your own accounts and authorized security research in accordance with our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Reviewed for this release: October 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Browser OSINT Tool & Web Username Scanner | MyRecon',
  description: 'Run OSINT investigations directly in your web browser with zero CLI setup. Search usernames across 500+ platforms, check data breaches, and audit DNS online.',
  keywords: 'browser osint tool, web browser osint scanner, online osint browser, no install osint tool, browser username lookup, sherlock browser alternative, maigret web alternative, client side osint scanner, browser digital footprint checker',
  url: `${site}/browser.html`,
  outFileName: 'browser.html',
  crumbLabel: 'Browser OSINT tool',
  questions: browserQuestions,
  bodyHtml: browserBody,
});

// 7. Digital footprint goal & privacy audit checklist page (/goal.html)
const goalQuestions = [
  ['What is a realistic digital footprint goal?', 'A realistic digital footprint goal is not total invisibility, but deliberate control over what the public internet reveals about you: closing forgotten accounts, unlinking reused handles, locking down active social profiles, rotating breached credentials, and opting out of people-search data brokers.'],
  ['How do I start a zero-exposure privacy goal with MyRecon?', 'Begin by cataloging your current public exposure. Run your primary and legacy usernames through the MyRecon username scanner, check your email addresses for historical data breaches, and list every public profile you no longer actively use.'],
  ['Why does username reuse work against my privacy goals?', 'When you use the exact same handle across professional networks, gaming sites, and casual forums, anyone can correlate those accounts in seconds. Separating handles by context breaks the link between your public identity and personal hobbies.'],
  ['How often should I review my digital footprint goals?', 'Run a self-audit every quarter or whenever you receive a breach notification. Data brokers periodically re-scrape public records, and newly disclosed breaches can expose older accounts you forgot registering.'],
  ['What if I find exposed records I do not have time to remove manually?', 'You can follow our free step-by-step account deletion and data broker opt-out guides in the MyRecon Privacy library, or request hands-on assistance through the MyRecon personal footprint removal service.'],
];

const goalBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Digital footprint goal</span></nav>
  <h1>Digital footprint goal and personal privacy audit roadmap</h1>
  <p class="sub">Set and achieve a measurable digital privacy goal. Map your public usernames across 500+ platforms, remediate email breach exposures, close dormant accounts, and opt out of data brokers step by step.</p>
  <a class="btn btn-primary" href="/#tool">Start your privacy goal audit</a>
  <p class="discovery-note">Structured self-audit workflow. Free Quick scans across 100 platforms; 500+ platforms with free sign-in. Built for consent-based personal privacy cleanup.</p>
  <section>
    <h2>Defining your personal digital footprint goal</h2>
    <p>Most people accumulate dozens of forgotten online accounts, public forum profiles, and data-broker records over a decade of internet use. Setting a clear digital footprint goal turns an overwhelming cleanup into a structured, verifiable checklist.</p>
    <dl>
      <dt><strong>Milestone 1: Full visibility</strong></dt>
      <dd>Discover every public profile tied to your current and historical usernames and identify which email addresses appear in public breach archives.</dd>
      <dt><strong>Milestone 2: Credential containment</strong></dt>
      <dd>Replace any reused or breached passwords, move two-factor authentication off SMS to an authenticator app or passkey, and revoke stale sessions.</dd>
      <dt><strong>Milestone 3: Account and broker reduction</strong></dt>
      <dd>Delete unused social and forum accounts at the source and submit opt-out requests to major people-search data brokers.</dd>
    </dl>
  </section>
  <section>
    <h2>5-step roadmap to reach your privacy goal</h2>
    <ol>
      <li><strong>Audit your handles:</strong> Run your known usernames through the <a href="/digital-footprint-checker.html">digital footprint checker</a> and <a href="/username-checker.html">username checker</a> to see what is publicly visible today.</li>
      <li><strong>Check email breach exposure:</strong> Scan your email addresses and follow our <a href="/guides/check-email-data-breach.html">email data breach guide</a> to prioritize high-risk accounts.</li>
      <li><strong>Delete dormant profiles:</strong> Use our <a href="/blog/find-your-own-old-accounts.html">old account discovery guide</a> and <a href="/privacy/">account deletion instructions</a> to close accounts you no longer need.</li>
      <li><strong>Break handle correlation:</strong> Review our <a href="/guides/reduce-your-digital-footprint.html">digital footprint reduction guide</a> to separate public professional profiles from private aliases.</li>
      <li><strong>Schedule quarterly re-checks:</strong> Use the <a href="/blog/own-footprint-audit-checklist.html">personal footprint audit checklist</a> to verify that removed listings stay offline.</li>
    </ol>
  </section>
  <section>
    <h2>Tools and guides to support your privacy goal</h2>
    <ul>
      <li><a href="/digital-footprint-checker.html">Free digital footprint checker and exposure audit</a></li>
      <li><a href="/free-osint-tool.html">Free OSINT tool and online investigation platform</a></li>
      <li><a href="/boost.html">Boost OSINT investigations and parallel sweeps</a></li>
      <li><a href="/browser.html">Browser OSINT tool and web username scanner</a></li>
      <li><a href="/reverse-username-lookup.html">Reverse username lookup across 500+ platforms</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
      <li><a href="/privacy/">Account deletion and data broker opt-out library</a></li>
      <li><a href="/guides/">OSINT and personal security guides</a></li>
      <li><a href="/services.html">Personal footprint removal service</a></li>
      <li><a href="/pricing.html">Plans and scan limits</a></li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions about digital footprint goals</h2>
    <div class="faq">${goalQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Consent-based self-audits and privacy ethics</h2>
    <p>MyRecon is designed to help you understand and reduce your own public exposure or conduct authorized security reviews. A matching handle is a lead to verify, not proof of identity. Review our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Reviewed for this release: October 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Digital Footprint Goal & Privacy Audit Roadmap | MyRecon',
  description: 'Achieve your digital privacy and zero-exposure footprint goals with MyRecon. Audit public usernames across 500+ platforms, check email leaks, and remove data.',
  keywords: 'digital footprint goal, privacy audit goal, zero digital footprint goal, online exposure reduction goal, personal cybersecurity goal, check digital footprint free, digital hygiene checklist, reduce online footprint goal, privacy cleanup roadmap',
  url: `${site}/goal.html`,
  outFileName: 'goal.html',
  crumbLabel: 'Digital footprint goal',
  questions: goalQuestions,
  bodyHtml: goalBody,
});



// 8. Product Walkthrough Watch Page (Primary VideoObject)
const watchQuestions = [
  ['What is shown in the MyRecon product walkthrough video?', 'The walkthrough demonstrates running multi-platform username sweeps across 500+ sources, checking email breach exposures with k-anonymity, auditing digital footprints, and performing privacy cleanup without command-line dependencies.'],
  ['How does MyRecon prevent false positives during username searches?', 'As shown in the video, MyRecon tests synthetic negative controls to detect platform false positives, wildcard matching, and HTTP 200 soft-404 redirects before returning verified public profile leads.'],
  ['Can I try the search features shown in the video for free?', 'Yes. Guests can run free Quick sweeps without creating an account or providing payment information. Standard scans across 500+ platforms are available with a free account.'],
  ['Where is the video hosted?', 'The product walkthrough video is embedded using YouTube\'s privacy-enhanced domain (youtube-nocookie.com), which does not set tracking cookies until the user initiates playback.'],
  ['How can I audit or remove accounts found during a search?', 'MyRecon provides direct links to official platform deletion pages, opt-out request forms for data brokers, and step-by-step privacy audit guides in our resource library.'],
];

const watchBody = `<main id="main" class="container prose discovery-page watch-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Product Walkthrough</span></nav>
  <h1>MyRecon Product Walkthrough &amp; Video Tour</h1>
  <p class="lead">Watch a 2-minute overview of MyRecon's public username search, data breach exposure checks, and digital footprint audit workflow.</p>
  
  <section class="watch-player-section" style="margin: 28px 0;">
    <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:12px;border:1px solid var(--border);background:#151515;">
      <iframe src="https://www.youtube-nocookie.com/embed/JysZLBTrdc4" title="MyRecon Product Walkthrough" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>
    </div>
  </section>

  <section>
    <h2>What you'll see in this video</h2>
    <ul>
      <li><strong>0:00 — High-Speed Username Sweeps</strong>: Querying 500+ platforms in parallel to discover public profile leads.</li>
      <li><strong>0:45 — Email &amp; Breach Exposure</strong>: Inspecting exposed databases without revealing sensitive credentials.</li>
      <li><strong>1:15 — Synthetic Control &amp; Verification</strong>: Eliminating soft-404 false positives and ghost accounts.</li>
      <li><strong>1:45 — Privacy Cleanup &amp; Deep Search</strong>: Moving from intelligence leads to data broker removals and opt-outs.</li>
    </ul>
  </section>

  <section>
    <h2>Try MyRecon after watching</h2>
    <p>Jump directly into the free OSINT investigation workspace:</p>
    <ul>
      <li><a href="/">Launch MyRecon username search console</a></li>
      <li><a href="/username-checker.html">Use the web username checker</a></li>
      <li><a href="/boost.html">Boost OSINT investigation speed and parallel sweeps</a></li>
      <li><a href="/browser.html">Browser OSINT tools and public scanning</a></li>
      <li><a href="/goal.html">Set and track a zero-footprint privacy goal</a></li>
      <li><a href="/directory.html">Browse the complete 400+ page research directory</a></li>
    </ul>
  </section>

  <section>
    <h2>Frequently asked questions about the video walkthrough</h2>
    <div class="faq">${watchQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>

  <section>
    <h2>Consent-based self-audits and privacy ethics</h2>
    <p>MyRecon is designed to help you understand and reduce your own public exposure or conduct authorized security reviews. A matching handle is a lead to verify, not proof of identity. Review our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Reviewed for this release: October 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'MyRecon Product Walkthrough & Video Tour | OSINT Tools',
  description: 'Watch the official MyRecon product walkthrough. Learn how to search public usernames across 500+ platforms, check breach exposures, and audit your digital footprint.',
  keywords: 'myrecon product video, myrecon walkthrough, osint tool demo, username search video, reverse username lookup tutorial, digital footprint video guide, free osint tool walkthrough, myrecon tutorial, online privacy video tour',
  url: `${site}/watch.html`,
  outFileName: 'watch.html',
  crumbLabel: 'Product walkthrough',
  questions: watchQuestions,
  bodyHtml: watchBody,
  videoObject: {
    '@type': 'VideoObject',
    '@id': `${site}/watch.html#video`,
    name: 'MyRecon Product Walkthrough: OSINT & Digital Footprint Research',
    description: 'Watch how MyRecon searches public usernames across 500+ platforms, detects data breach exposures, and helps you audit and clean up your online digital footprint.',
    thumbnailUrl: [`${site}/assets/img/og-image.png`],
    uploadDate: '2026-10-18T08:00:00+00:00',
    duration: 'PT2M15S',
    contentUrl: 'https://www.youtube.com/watch?v=JysZLBTrdc4',
    embedUrl: 'https://www.youtube-nocookie.com/embed/JysZLBTrdc4',
    publisher: {
      '@type': 'Organization',
      '@id': `${site}/#organization`,
      name: 'MyRecon',
      url: `${site}/`,
      logo: {
        '@type': 'ImageObject',
        url: `${site}/assets/img/og-image.png`,
        width: 1200,
        height: 630,
      },
    },
  },
});
