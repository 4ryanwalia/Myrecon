/* Keep public discovery and tool landing pages in the production static build. */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const site = 'https://www.myrecon.xyz';

function buildDiscoveryPage({ title, description, keywords, url, outFileName, crumbLabel, questions, bodyHtml, videoObject, webApplication, modifiedAt = '2026-10-18' }) {
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

  if (videoObject) {
    graph['@graph'].push(videoObject);
  }
  if (webApplication) {
    graph['@graph'].push(webApplication);
  }
  const discoveryCss = /\/assets\/(?:optimized\/)?css\/discovery(?:\.[a-f0-9]{12})?\.css/.test(html) ? '' : '<link rel="stylesheet" href="/assets/css/discovery.css">\n';
  html = html.replace('</head>', `${discoveryCss}<script type="application/ld+json">${JSON.stringify(graph).replace(/</g, '\\u003c')}</script>\n</head>`);
  html = html.replace(/<main\b[^>]*>.*?<\/main>/s, bodyHtml);

  // Defuse render-blocking recommendation-analytics.js in <head>
  html = html.replace(/(<script\b(?![^>]*\bdefer\b)[^>]*src="[^"]*recommendation-analytics[^"]*")/i, '$1 defer');

  // Replace heavy search application with lightweight editorial shell
  html = html.replace(/<script\b[^>]*src="[^"]*\/(?:assets\/(?:optimized\/)?js\/)?app(?:\.[a-f0-9]{12})?\.js(?:\?[^"]*)?"[^>]*><\/script>/gi, '<script src="/assets/js/editorial-shell.js" defer></script>');
  html = html.replace(/<script\b[^>]*src="[^"]*\/(?:assets\/(?:optimized\/)?js\/)?(?:env|config)(?:\.[a-f0-9]{12})?\.js(?:\?[^"]*)?"[^>]*><\/script>\s*/gi, '');

  if (/<username-search-input\b/i.test(bodyHtml) && !/username-search-input\.js/i.test(html)) {
    html = html.replace(/<\/body>/i, '  <script src="/assets/js/username-search-input.js" defer></script>\n</body>');
  }

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
  ['Is the username checker free?', 'MyRecon offers free guest Quick scans across 100 platforms with no sign-up required. Guests get 5 Quick scans daily with only the first 2 result cards visible. Signed-in free accounts get 5 Standard scans daily across 560+ platforms; Quick and Standard share that account allowance. Paid plans add features such as Deep Search and Extended scans; check the current pricing page for limits.'],
  ['Can I search every social media platform?', 'No. MyRecon checks a supported catalogue of more than 500 platforms, not every website. Login walls, anti-bot controls, timeouts and platform changes can leave a check unknown.'],
  ['How do I find my old accounts by username?', 'Search handles you remember using, then open each candidate profile and compare it with your own records. Use saved passwords, signup emails and the official account recovery process to confirm ownership.'],
];

const usernameBody = fs.readFileSync(path.join(root, 'content/discovery/username-checker.html'), 'utf8')
  .replace('<!-- faq -->', usernameQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join(''));

buildDiscoveryPage({
  title: 'Username Lookup & Social Media Username Checker | MyRecon',
  description: 'Check public usernames across 560+ platforms with MyRecon. Review social media profile leads, unknown results and username availability limits.',
  keywords: 'username checker, social media username search, username lookup, check username across platforms, find accounts by username, public profile search, handle checker, username availability vs search, browser username checker, osint username search',
  url: `${site}/username-checker.html`,
  outFileName: 'username-checker.html',
  crumbLabel: 'Username checker',
  questions: usernameQuestions,
  bodyHtml: usernameBody,
  modifiedAt: '2026-11-01',
});

// 2. Free OSINT tool discovery page
const osintQuestions = [
  ['What is a free OSINT tool?', 'An OSINT (Open-Source Intelligence) tool collects and analyzes information from publicly accessible online sources, such as social platforms, developer profiles, breach repositories, domain registrations, and DNS records. MyRecon provides a free browser-based OSINT scanner to map your digital footprint or conduct authorized security investigations without installing software.'],
  ['Is MyRecon really free to use for OSINT investigations?', 'Yes. MyRecon provides free guest Quick scans across 100 platforms with zero setup or sign-in required. Users with an account can run Standard scans across 560+ platforms, query email breach exposure, check password exposure via k-anonymity, and audit domain DNS configurations at no cost. Paid plans add Deep Search and Extended 3,000+ platform sweeps.'],
  ['How does MyRecon compare to CLI tools like Sherlock and Maigret?', 'Command-line tools like Sherlock and Maigret require Python environments, Git, and package management, running requests from your terminal IP. MyRecon runs directly in your web browser or Android app with zero installation. Additionally, MyRecon tests against synthetic control handles to eliminate false-positive 200 OK responses and integrates email breach and DNS intelligence in a unified dashboard.'],
  ['Can a free OSINT tool find private or hidden social accounts?', 'No. Legitimate OSINT tools only query publicly accessible endpoints, indexed profiles, and public registries. They do not bypass passwords, exploit vulnerabilities, or intercept private communications. If a profile is restricted, suspended, or behind a login wall, MyRecon transparently reports the result as unknown rather than assuming it is absent.'],
  ['What investigation modules are included in MyRecon\'s free OSINT suite?', 'MyRecon includes reverse username search across 560+ platforms, email breach detection against billions of compromised records, password leak checking using k-anonymity SHA-1 prefixes, domain WHOIS and RDAP registration lookup, and DNS mail-authentication checks for SPF and DMARC spoofing defense.'],
];

const osintBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Free OSINT tool</span></nav>
  <h1>Free OSINT tool and online investigation platform</h1>
  <p class="sub">MyRecon is a browser-based Open-Source Intelligence (OSINT) platform for reverse username search, digital footprint audits, email breach detection, and domain intelligence across 560+ sources. Search instantly with zero installation.</p>
  <a class="btn btn-primary" href="/#tool">Start free OSINT investigation</a>
  <p class="discovery-note">Zero setup required. Free guest Quick scans across 100 platforms. Standard scans cover 560+ platforms. Ethical public-source research only.</p>
  <section>
    <h2>What is an OSINT tool and how does it work?</h2>
    <p>Open-Source Intelligence (OSINT) refers to intelligence derived from publicly accessible data. A free OSINT tool automates the collection and correlation of public data across social networks, developer hubs, public registries, and breached credential archives.</p>
    <p>Instead of manually visiting hundreds of websites, MyRecon queries public profile endpoints simultaneously. On the full scan that comes with free sign-in, a check with no direct profile evidence is also compared with a made-up control handle on the same platform. Every check ends in one of three evidence states:</p>
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
      <li><strong>Reverse username lookup:</strong> Sweep handles across 560+ platforms, including Instagram, GitHub, TikTok, Reddit, X (Twitter), Discord, and YouTube. Read our <a href="/username-checker.html">username checker guide</a> and <a href="/reverse-username-lookup.html">reverse username search overview</a>.</li>
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
    <p>Traditional open-source intelligence tools like Sherlock and Maigret are built as command-line terminal scripts. While powerful for developers, they present operational friction:</p>
    <ul>
      <li><strong>Installation overhead:</strong> CLI tools require Python, pip package dependencies, and terminal environments. MyRecon runs instantly in any modern browser on desktop or mobile.</li>
      <li><strong>Rate limiting and IP burning:</strong> Running high-speed terminal sweeps from a personal home IP often triggers CAPTCHAs and temporary IP bans. MyRecon balances query distribution to maintain reliability.</li>
      <li><strong>False-positive elimination:</strong> Many platforms return HTTP 200 responses for nonexistent accounts. MyRecon looks for direct profile evidence first and, on signed-in scans, compares unclear pages with an impossible control handle so ghost accounts are not reported as found.</li>
      <li><strong>Integrated intelligence:</strong> CLI tools typically focus only on usernames. MyRecon combines usernames, email breaches, password exposure, and domain DNS analysis in one view.</li>
    </ul>
    <p>See our head-to-head technical comparisons: <a href="/vs/sherlock.html">MyRecon vs Sherlock</a>, and <a href="/vs/">all OSINT tool comparisons</a>.</p>
  </section>
  <section>
    <h2>Featured OSINT resources and tools</h2>
    <p>Explore our research library, cheat sheets, and specialized investigation workflows:</p>
    <ul>
      <li><a href="/digital-footprint-checker.html">Digital footprint checker &amp; exposure audit</a></li>
      <li><a href="/reverse-username-lookup.html">Reverse username lookup across 560+ platforms</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
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
  description: 'Free OSINT tool to search usernames across 560+ platforms, check email breach exposure, and audit digital footprints. Start your free investigation online.',
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
  ['What is a digital footprint checker?', 'A digital footprint checker helps you review parts of your online exposure. MyRecon can find public username profile leads and check an email against supported breach sources. Results may be incomplete, so verify matches and review your own account records.'],
  ['How do I check my digital footprint for free?', 'Choose a username check for public profile leads or an email check for supported breach exposure. Free guest Quick username scans cover 100 platforms with limited visible results; Standard scans require sign-in. Review current plan limits and verify each result at its source.'],
  ['What is the difference between active and passive digital footprints?', 'An active digital footprint consists of data you intentionally post online, such as social media posts, public profiles, and forum discussions. A passive digital footprint includes data collected about you without your direct action, such as data broker listings, breach corpora, and server logs. MyRecon checks supported public profiles and breach sources; it cannot audit every passive record or server log.'],
  ['How can I clean up or reduce my digital footprint?', 'Start by reviewing public profile leads and supported email breach results with MyRecon, then confirm your own accounts using saved logins and signup messages. Delete dormant accounts, request opt-outs from people-search data brokers, enable two-factor authentication on critical services, and replace breached passwords. Follow our digital footprint reduction guide for step-by-step instructions.'],
  ['Does a digital footprint check affect my credit score or alert anyone?', 'MyRecon checks supported public sources and breach data; it is not a credit check. Requests can be logged by source services, so do not assume research is invisible. It does not grant access to private accounts.'],
];

const footprintBody = fs.readFileSync(path.join(root, 'content/discovery/digital-footprint-checker.html'), 'utf8')
  .replace('<!-- faq -->', footprintQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join(''));

buildDiscoveryPage({
  title: 'Digital Footprint Checker by Email & Username | MyRecon',
  description: 'Check public username profiles and email breach exposure. Learn what each result means and follow practical steps to reduce your digital footprint.',
  keywords: 'digital footprint checker, free digital footprint checker, digital footprint search, digital footprint audit, check digital footprint free, online footprint audit, how to check digital footprint, digital footprint scanner, reverse digital footprint, personal privacy audit, privacy goal checklist, digital footprint cleanup goal, zero footprint goal, check online exposure free, search digital footprint by name',
  url: `${site}/digital-footprint-checker.html`,
  outFileName: 'digital-footprint-checker.html',
  crumbLabel: 'Digital footprint checker',
  questions: footprintQuestions,
  bodyHtml: footprintBody,
  modifiedAt: '2026-11-01',
});

// 4. Reverse username lookup discovery page
const lookupQuestions = [
  ['What is a reverse username lookup?', 'A reverse username lookup is an OSINT reconnaissance technique that takes a single username or handle and queries hundreds of web platforms to identify registered public profiles associated with that handle.'],
  ['Is reverse username lookup free on MyRecon?', 'Yes. MyRecon allows anyone to run free guest Quick scans across 100 platforms with no login required. Creating a free account unlocks Standard scans across 560+ platforms with complete result cards, exportable summaries, and saved search history.'],
  ['How does reverse username search differ from searching Google?', 'Traditional search engines only index pages that have been discovered and crawled, often missing new profiles, profile changes, and niche platforms. A reverse username lookup queries the platform\'s public URL endpoint directly in real time, detecting accounts even if Google has not indexed them.'],
  ['How does MyRecon prevent false positives during username searches?', 'Many social networks return HTTP 200 OK status codes for non-existent users (soft 404s). MyRecon first looks for direct evidence, such as an API user record or profile markup naming the handle. On signed-in scans, when that evidence is missing, it also fetches a made-up control handle on the same platform, and if the site responds identically for both, the result is not reported as found. Guest Quick scans rely on soft-404 and login-wall detection instead.'],
  ['Can a reverse username search prove who owns an account?', 'No. A matching username is an investigative lead, not conclusive proof of identity. Different people can independently choose the same handle on different websites. Always verify account ownership by reviewing profile content, joined dates, and cross-linked social profiles.'],
];

const lookupBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Reverse username lookup</span></nav>
  <h1>Free reverse username lookup &amp; social media account search</h1>
  <p class="sub">Query handles across 560+ social platforms, developer hubs, and forums simultaneously. Discover profile leads, cut false positives with control-handle checks on signed-in scans, and map online accounts instantly.</p>
  <a class="btn btn-primary" href="/#tool=username">Start reverse username lookup</a>
  <p class="discovery-note">No terminal setup required. Free guest Quick scans across 100 platforms. Standard scans cover 560+ platforms. Public evidence research only.</p>
  <section>
    <h2>What is reverse username lookup and how does it work?</h2>
    <p>A reverse username search takes a known handle, alias, or screen name and probes hundreds of online services to find matching public profiles. Because people frequently reuse the same username across different websites, a reverse lookup connects fragmented profiles into a unified digital footprint.</p>
    <p>Instead of manual searching or maintaining complex command-line scripts, MyRecon runs browser-based multi-threaded queries against 560+ platforms including Instagram, GitHub, Reddit, TikTok, X (Twitter), YouTube, Discord, and Telegram.</p>
  </section>
  <section>
    <h2>How to perform an effective reverse username search</h2>
    <ol>
      <li><strong>Enter the target username:</strong> Input the exact handle into the <a href="/#tool=username">reverse username tool</a>.</li>
      <li><strong>Choose your scan scope:</strong> Start with a Quick scan (100 top platforms) or sign in for a Standard scan covering 560+ platforms.</li>
      <li><strong>Evaluate evidence-backed states:</strong> Review results categorized as found, not found, or unknown. MyRecon never guesses; if a site rate-limits or blocks a query, it remains unknown.</li>
      <li><strong>Verify leads at the source:</strong> Click the reported profile URLs to confirm account activity, creation dates, and public profile bios. Read our guide on <a href="/guides/verify-osint-account-matches.html">verifying OSINT account matches</a>.</li>
    </ol>
  </section>
  <section>
    <h2>Overcoming false positives: The synthetic control advantage</h2>
    <p>One major flaw in traditional CLI username tools like Sherlock and Maigret is susceptibility to soft 404s. Many modern web applications return an HTTP 200 OK status code with a "user not found" splash screen or redirect to a landing page, causing terminal tools to report ghost accounts.</p>
    <p>On signed-in scans, MyRecon handles this with a control handle. When a page gives no direct profile evidence, it fetches an impossible handle on the same platform. If both responses look the same, MyRecon reports not found or unknown rather than claiming an account was found. Guest Quick scans use soft-404 and login-wall detection instead. Read our research on <a href="/guides/why-username-checkers-report-fake-accounts.html">why username checkers report fake accounts</a>.</p>
  </section>
  <section>
    <h2>How do you corroborate a username match?</h2>
    <p>A matching handle is a lead, not proof that two accounts belong to the same person. Before you treat a match as the same owner, look for at least one of these independent signals:</p>
    <ul>
      <li><strong>Cross-linked bios:</strong> one profile links to the other, or both link to the same personal site or verified handle.</li>
      <li><strong>Matching images:</strong> the same avatar or photo crop appears on both accounts.</li>
      <li><strong>Consistent timelines:</strong> creation dates and early posts fit one person's history. A 2012 account about college and a 2024 account run by a teenager are probably different people.</li>
      <li><strong>Writing and activity patterns:</strong> the same phrasing, posting hours and communities across both accounts.</li>
    </ul>
    <p>See <a href="/guides/verify-osint-account-matches.html">how to verify OSINT account matches</a> for the full review checklist.</p>
  </section>
  <section>
    <h2>Worked example: a reused hobby handle</h2>
    <p>Say you used <code>example_handle_27</code> on a forum and a photo service years ago. A lookup now returns those two pages and a third profile on another service. Your saved logins confirm the forum and your signed-in session confirms the photo account. You have no ownership evidence for the third result, so it stays unconfirmed. You can clean up the first two without assigning a stranger's information to yourself.</p>
    <p>The example is illustrative. A useful audit counts completed corrections, not matching URLs. Keep your notes private, store only the evidence you need, and revisit unresolved entries only when new information would change what you do.</p>
  </section>
  <section>
    <h2>Related OSINT investigation tools</h2>
    <ul>
      <li><a href="/free-osint-tool.html">Free OSINT tool and online investigation platform</a></li>
      <li><a href="/digital-footprint-checker.html">Free digital footprint checker and online audit</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
      <li><a href="/deep-search.html">Deep Search: public comments and mentions</a></li>
      <li><a href="/username-sweep-vs-deep-search.html">Username Sweep vs Deep Search workflow comparison</a></li>
      <li><a href="/blog/best-username-search-tools.html">Best username search tools: evidence and workflow</a></li>
      <li><a href="/guides/verify-osint-account-matches.html">How to verify OSINT account matches</a></li>
      <li><a href="/vs/sherlock">MyRecon vs Sherlock comparison</a></li>
      <li><a href="/blog/best-data-breach-checkers.html">Data breach checkers compared</a></li>
      <li><a href="/guides/people-search-apps-what-they-find.html">What people-search apps actually find</a></li>
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
  description: 'Free reverse username lookup to search handles across 560+ social media networks, forums, and developer sites. Check accounts with zero installation.',
  keywords: 'reverse username lookup, reverse username search, reverse username search free, free reverse username lookup, social media username search, find accounts by username, username lookup, reverse social media lookup, browser reverse username lookup, sherlock online alternative, maigret alternative online, search username across social media, find someone by username',
  url: `${site}/reverse-username-lookup.html`,
  outFileName: 'reverse-username-lookup.html',
  crumbLabel: 'Reverse username lookup',
  questions: lookupQuestions,
  bodyHtml: lookupBody,
});

// 5-7. /boost.html, /browser.html and /goal.html were retired on 2026-11-17
// after the fifth AdSense "low value content" notice: three keyword landing
// pages ("boost osint", "browser osint tool", "digital footprint goal") that
// all funnelled to the same scanner are doorway pages under Google's spam
// policies. They 308 to /free-osint-tool.html and /digital-footprint-checker.html
// (vercel.json + content/editorial-redirects.json). Do not rebuild them.

// 8. Product Walkthrough Watch Page (Primary VideoObject)
const watchQuestions = [
  ['How long is the MyRecon product video?', 'The MyRecon product video runs for 60 seconds. Use the current product pages and guides for detailed workflows, supported checks and plan limits.'],
  ['Does a username match prove who owns an account?', 'No. A matching handle is a public-profile lead. Open the original source and compare independent evidence before attributing the profile to someone. Blocks, timeouts and ambiguous responses can leave a check unknown.'],
  ['Can I try the search features shown in the video for free?', 'Yes. Guests can run free Quick sweeps without creating an account or providing payment information. Standard scans across 560+ platforms are available with a free account.'],
  ['Where is the video hosted?', 'This page embeds YouTube\'s privacy-enhanced player at youtube-nocookie.com. YouTube provides playback; review the relevant privacy policies before watching.'],
  ['How can I audit or remove accounts found during a search?', 'First confirm which accounts are yours. Review their public details and use the official service settings to secure, change or delete them. MyRecon\'s privacy guides explain the process and its limits; a search result does not automatically remove an account.'],
];

const watchBody = `<main id="main" class="container prose discovery-page watch-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Product Walkthrough</span></nav>
  <h1>MyRecon Product Walkthrough &amp; Video Tour</h1>
  <p class="lead">Watch the 60-second MyRecon product video, then explore the current username-search and digital-footprint workflows.</p>
  
  <section class="watch-player-section" style="margin: 28px 0;">
    <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:12px;border:1px solid var(--border);background:#151515;">
      <iframe src="https://www.youtube-nocookie.com/embed/JysZLBTrdc4" title="MyRecon Product Walkthrough" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;"></iframe>
    </div>
  </section>

  <section>
    <h2>Continue with a step-by-step workflow</h2>
    <p>Start with a handle you use or have permission to research. Open candidate profiles at their original service and keep uncertain results separate. For your own accounts, compare saved logins and signup records before choosing a privacy or account-security action.</p>
    <p>For email breach exposure, follow the <a href="/guides/check-email-data-breach.html">email breach-check guide</a>. A breach result describes reported exposure in supported sources; it does not list every account registered to an address.</p>
  </section>

  <section>
    <h2>Try MyRecon after watching</h2>
    <p>Jump directly into the free OSINT investigation workspace:</p>
    <ul>
      <li><a href="/">Launch MyRecon username search console</a></li>
      <li><a href="/username-checker.html">Use the web username checker</a></li>
      <li><a href="/free-osint-tool.html">Free OSINT tool overview</a></li>
      <li><a href="/digital-footprint-checker.html">Check your own digital footprint</a></li>
      <li><a href="/directory.html">Browse the research directory</a></li>
    </ul>
  </section>

  <section>
    <h2>Frequently asked questions about the video walkthrough</h2>
    <div class="faq">${watchQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>

  <section>
    <h2>Consent-based self-audits and privacy ethics</h2>
    <p>MyRecon is designed to help you understand and reduce your own public exposure or conduct authorized security reviews. A matching handle is a lead to verify, not proof of identity. Review our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Updated October 20, 2026. <a href="/pricing">Current plans and limits</a>.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'MyRecon Product Walkthrough & Video Tour | OSINT Tools',
  description: 'Watch the 60-second MyRecon product video and explore guides for public username search, email breach exposure and your own digital-footprint audit.',
  keywords: 'myrecon product video, myrecon walkthrough, osint tool demo, username search video, reverse username lookup tutorial, digital footprint video guide, free osint tool walkthrough, myrecon tutorial, online privacy video tour',
  url: `${site}/watch.html`,
  outFileName: 'watch.html',
  crumbLabel: 'Product walkthrough',
  questions: watchQuestions,
  bodyHtml: watchBody,
  modifiedAt: '2026-10-20',
  videoObject: {
    '@type': 'VideoObject',
    '@id': `${site}/watch.html#video`,
    name: 'MyRecon Product Walkthrough: OSINT & Digital Footprint Research',
    description: 'A 60-second introduction to MyRecon, accompanied by links to current public-source research and digital-footprint guides.',
    thumbnailUrl: ['https://i.ytimg.com/vi/JysZLBTrdc4/hqdefault.jpg'],
    uploadDate: '2026-10-13T11:44:41+05:30',
    duration: 'PT1M',
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
