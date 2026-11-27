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

  // Replace heavy search application with lightweight editorial shell
  html = html.replace(/<script\b[^>]*src="[^"]*\/(?:assets\/(?:optimized\/)?js\/)?app(?:\.[a-f0-9]{12})?\.js(?:\?[^"]*)?"[^>]*><\/script>/gi, '<script src="/assets/js/editorial-shell.js" defer></script>');
  html = html.replace(/<script\b[^>]*src="[^"]*\/(?:assets\/(?:optimized\/)?js\/)?(?:env|config)(?:\.[a-f0-9]{12})?\.js(?:\?[^"]*)?"[^>]*><\/script>\s*/gi, '');

  if (/<username-search-input\b/i.test(bodyHtml) && !/username-search-input\.js/i.test(html)) {
    html = html.replace(/<\/body>/i, '  <script src="/assets/js/username-search-input.js" defer></script>\n</body>');
  }

  if (/id="discord-lookup-form"/.test(bodyHtml) && !/discord-id-lookup\.js/i.test(html)) {
    html = html.replace(/<\/body>/i, '  <script src="/assets/js/env.js"></script>\n  <script src="/assets/js/discord-id-lookup.js" defer></script>\n</body>');
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
  ['Is the username checker free?', 'MyRecon offers free guest Quick scans across 100 platforms with no sign-up required. Guests get 5 Quick scans daily with up to 5 result cards shown in full, strongest matches first. Signed-in free accounts get 5 Standard scans daily across 560+ platforms; Quick and Standard share that account allowance. Paid plans add features such as Deep Search and Extended scans; check the current pricing page for limits.'],
  ['Can I search every social media platform?', 'No. MyRecon checks a supported catalogue of more than 500 platforms, not every website. Login walls, anti-bot controls, timeouts and platform changes can leave a check unknown.'],
  ['How do I find my old accounts by username?', 'Search handles you remember using, then open each candidate profile and compare it with your own records. Use saved passwords, signup emails and the official account recovery process to confirm ownership.'],
];

const usernameBody = fs.readFileSync(path.join(root, 'content/discovery/username-checker.html'), 'utf8')
  .replace('<!-- faq -->', usernameQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join(''));

buildDiscoveryPage({
  title: 'Free Username Checker for 560+ Sites | MyRecon',
  description: 'Run a free username checker across 560+ public platforms. See guest limits, verify live profile leads and test handle registration rules safely.',
  keywords: 'username checker, free username checker, username lookup tool, social media username search, check username across platforms, find accounts by username, public profile search, osint username search',
  url: `${site}/username-checker.html`,
  outFileName: 'username-checker.html',
  crumbLabel: 'Username checker',
  questions: usernameQuestions,
  bodyHtml: usernameBody,
  modifiedAt: '2026-11-27',
});

// 2. Free OSINT tool discovery page
const osintQuestions = [
  ['What is a free OSINT tool?', 'An open-source intelligence tool helps you collect and review publicly accessible information. MyRecon combines browser tools for checking your own public usernames, email breach exposure and domain records.'],
  ['Can I use MyRecon without signing in?', 'Yes. Run a guest Quick username check across 100 supported platforms with up to five result cards visible. Email breach results are available to guests. Sign in for five free Standard username searches per day across 560+ supported platforms, with complete result cards.'],
  ['How does MyRecon compare to Sherlock and Maigret?', 'MyRecon offers username checks and other tools in a browser. Sherlock and Maigret run from your terminal and let you review their source and settings. Results from any tool should be checked against the original profile before you rely on a match.'],
  ['Can a free OSINT tool find private or hidden social accounts?', 'MyRecon searches supported public sources. A blocked request or a sign-in screen leaves the public profile check unresolved.'],
  ['What can I check for free?', 'MyRecon includes free public username checks, email breach lookup, password exposure checks and tools for reviewing domain registration, DNS and IP information. Read the plans page for account and usage limits.'],
];

const osintBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Free OSINT tool</span></nav>
  <h1>Free OSINT tools online for public self-audits</h1>
  <p class="sub">Use MyRecon's free browser OSINT tools to search a username, check an email address for reported breaches, or review public records for a domain you control.</p>
  <username-search-input sample="octocat"></username-search-input>
  <p>Starting from an email instead? Use the <a href="/reverse-email-lookup.html">reverse email lookup</a>.</p>
  <p class="discovery-note">Guest Quick checks cover 100 supported platforms and show up to five result cards. A free account includes five Standard username searches a day across 560+ supported platforms. <a href="/pricing">See current plans and limits.</a></p>
  <section>
    <h2 id="core-osint-investigation-modules">Choose a free OSINT tool</h2>
    <dl>
      <dt><strong><a href="/reverse-email-lookup.html">Check an email for breaches and linked accounts</a></strong></dt>
      <dd>See reported breaches and the types of data listed by supported sources. Returned breach results are available without signing in.</dd>
      <dt><strong><a href="/#tool">Find public profiles for a username</a></strong></dt>
      <dd>Use Quick for a guest preview or sign in for Standard results. Open each reported source to confirm the exact handle.</dd>
      <dt><strong>Check whether a password appeared in a breach</strong></dt>
      <dd><a href="/#tool">Open the toolbox</a> and choose Password. The browser hashes the password and sends only a short prefix of the hash.</dd>
      <dt><strong><a href="/#tool=domain">Review domain registration</a> or <a href="/#tool=dns">check DNS records</a></strong></dt>
      <dd>Review public information published for a domain you control, including mail settings such as SPF and DMARC.</dd>
      <dt><strong><a href="/#tool=ip">Review public IP address information</a></strong></dt>
      <dd>See the reported network owner, approximate location and reverse DNS for an IP you manage.</dd>
    </dl>
  </section>
  <section>
    <h2>What is an OSINT tool and how does it work?</h2>
    <p>Open-Source Intelligence (OSINT) refers to intelligence derived from publicly accessible data. A free OSINT tool automates the collection and correlation of public data across social networks, developer hubs, public registries, and breached credential archives.</p>
    <p>Username checks can return evidence for a profile, report that a checked source did not find it, or stay unresolved. The verdict describes the response observed at that source.</p>
    <dl>
      <dt><strong>Found</strong></dt>
      <dd>The source provided evidence for a public profile. Check the exact handle and confirm any ownership claim independently.</dd>
      <dt><strong>Not found</strong></dt>
      <dd>The check reported absence at the address it tested. Availability for registration is a separate question.</dd>
      <dt><strong>Unknown</strong></dt>
      <dd>The response was unavailable or inconclusive. Treat it as unresolved when reviewing your results.</dd>
    </dl>
  </section>
  <section>
    <h2>How to conduct a free OSINT investigation</h2>
    <ol>
      <li>Choose the tool that matches your question, then enter an account or asset you own or are authorized to review.</li>
      <li>For a username check, choose Quick as a guest or Standard with a free account. Email, domain, DNS and IP checks have their own inputs.</li>
      <li>Record what the result actually shows. Check important claims at the linked source and note inaccessible sources separately. <a href="/guides/what-is-osint.html">Read the OSINT workflow guide.</a></li>
    </ol>
  </section>
  <section>
    <h2>Comparing free OSINT tools: Web scanner vs CLI scripts</h2>
    <p>Choose a browser tool for a quick check or a terminal tool if you want to inspect its settings and run it locally. Both can return inconclusive results. In <a href="/blog/username-search-benchmark-research.html#http-200-username-evidence">MyRecon's recorded study</a>, one GitLab fixture returned HTTP 200 on 20 attempts even though the official API found no account for it.</p>
    <p>Compare <a href="/vs/sherlock">MyRecon and Sherlock</a> or read the <a href="/blog/best-free-osint-tools-for-investigators.html">free OSINT tools guide</a> for options by task.</p>
  </section>
  <section>
    <h2>A beginner-friendly list of free OSINT websites</h2>
    <p>For a beginner-friendly list of free OSINT websites with zero terminal setup, pair one handle scanner, one breach checker, one domain lookup, and one web archive. Each OSINT online tool or reconnaissance website answers a different public-source question and lets you verify leads directly at the source.</p>
    <ul>
      <li><strong>Username and OSINT platform search:</strong> <a href="/username-checker.html">MyRecon</a> (browser sweeps across 100 guest or 560+ signed-in platforms with explicit unknown verdicts) and <a href="/whatsmyname-alternatives.html">WhatsMyName migration alternatives</a>.</li>
      <li><strong>Email breach and password checks:</strong> <a href="/reverse-email-lookup.html">MyRecon reverse email lookup</a> and <a href="/vs/have-i-been-pwned.html">Have I Been Pwned</a> for historical breach datasets and k-anonymity password checks.</li>
      <li><strong>Domain, DNS and IP context:</strong> MyRecon's <a href="/#tool=domain">RDAP domain lookup</a>, <a href="/#tool=dns">DNS records</a>, and <a href="/#tool=ip">IP lookup</a>, alongside ICANN Lookup and crt.sh for certificate transparency logs.</li>
      <li><strong>Directory and beginner workflows:</strong> Read our <a href="/blog/free-osint-tools-for-beginners.html">beginner OSINT workflow</a> or compare top OSINT sites in our <a href="/blog/best-free-osint-tools-for-investigators.html">best OSINT tools guide</a> across open source intelligence tools and online investigation tools.</li>
    </ul>
  </section>
  <section>
    <h2>Featured OSINT resources and tools</h2>
    <p>Explore our research library, cheat sheets, and specialized investigation workflows:</p>
    <ul>
      <li><a href="/digital-footprint-checker.html">Digital footprint checker &amp; exposure audit</a></li>
      <li><a href="/reverse-username-lookup.html">Reverse username search &amp; lookup across 560+ platforms</a></li>
      <li><a href="/username-checker.html">Username checker and public profile search</a></li>
      <li><a href="/osint-cheat-sheet.html">OSINT cheat sheet &amp; Google dork generator</a></li>
      <li><a href="/deep-search.html">Deep Search: public activity &amp; mentions</a></li>
      <li><a href="/blog/best-free-osint-tools-for-investigators.html">Best free OSINT tools for investigators</a></li>
      <li><a href="/upcoming-osint-tools-2027.html">Upcoming OSINT tools (2026-2027)</a></li>
      <li><a href="/osint-glossary.html">OSINT glossary &amp; spelling clarifications</a></li>
      <li><a href="/blog/best-username-search-tools.html">Best OSINT username search tools compared</a></li>
      <li><a href="/find/github-profile">GitHub user search and profile lookup guide</a></li>
      <li><a href="/blog/instagram-username-search.html">Instagram username search guide</a></li>
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
    <p>Access reviewed <time datetime="2026-11-27">27 November 2026</time>.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Free OSINT Tools Online: Browser Suite | MyRecon',
  description: 'Use free OSINT tools in your browser with no install: search usernames across 560+ sites, check email breaches, and inspect DNS, WHOIS and IPs.',
  url: `${site}/free-osint-tool.html`,
  outFileName: 'free-osint-tool.html',
  modifiedAt: '2026-11-27',
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
  title: 'Digital Footprint Checker & Exposure Audit | MyRecon',
  description: 'Audit your digital footprint by email and public handle. Review breach exposure, verify old accounts and follow practical cleanup steps.',
  keywords: 'digital footprint checker, free digital footprint checker, digital footprint audit, online presence checker, check digital footprint free, personal privacy audit, footprint cleanup checklist',
  url: `${site}/digital-footprint-checker.html`,
  outFileName: 'digital-footprint-checker.html',
  crumbLabel: 'Digital footprint checker',
  questions: footprintQuestions,
  bodyHtml: footprintBody,
  modifiedAt: '2026-11-27',
});

// 4. Reverse username lookup discovery page
const lookupQuestions = [
  ['What is a reverse username lookup?', 'A reverse username lookup checks supported public sources for a handle you already know. It can return candidate links to public profiles for you to review.'],
  ['Is reverse username lookup free on MyRecon?', 'Guest Quick checks cover 100 supported platforms and show up to five result cards without a login. A free account includes five Standard username searches per day across 560+ supported platforms, with complete result cards.'],
  ['How does reverse username search differ from searching Google?', 'Google returns pages it has indexed. A reverse username lookup checks supported public sources directly, and some sources may block requests or give an unclear response.'],
  ['Why can reverse username search produce false positives?', 'A source can return HTTP 200 for a generic page or an error message. Open a source and check that it actually identifies the exact handle. If a source is blocked or ambiguous, keep the result unresolved.'],
  ['Can a reverse username search prove who owns an account?', 'A shared handle can belong to different people. For your own accounts, confirm access through the platform. For other authorized work, look for owner-published links or another independent source before connecting profiles.'],
];

const lookupBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Reverse username lookup</span></nav>
  <h1>Free reverse username search and lookup for public profiles</h1>
  <p class="sub">Use MyRecon to run a reverse username search from a handle or a full Instagram, TikTok or GitHub profile link, then review candidates by opening the original profile URLs.</p>
  <username-search-input sample="octocat"></username-search-input>
  <p class="discovery-note">Guest Quick covers 100 supported platforms and shows up to five result cards. A free account includes five Standard searches a day across 560+ supported platforms. <a href="/pricing">See current plans.</a></p>
  <p><a href="/videos/reverse-username-search.html">Watch the 32-second walkthrough</a> or <a href="/username-checker.html#observed-demo">see a recorded guest result</a>.</p>
  <section>
    <h2>What is reverse username lookup and how does it work?</h2>
    <p>A reverse username search checks where the same handle may appear across supported social networks, developer hubs, and forums. Whether you call it a username reverse lookup, username reverse search, or reverse search username check, it helps you find username reuse on your own forgotten accounts before confirming ownership directly at the source.</p>
    <p>Run a reverse username search free with no sign-up for a 100-site preview, or sign in for 560+ platforms. Unlike raw-status username lookup tools that flag login walls as hits, MyRecon labels blocked responses as unknown; a public handle sweep is also distinct from a numeric user id search such as a <a href="/discord-id-lookup.html">Discord ID lookup</a>.</p>
  </section>
  <section>
    <h2>How to perform an effective reverse username search</h2>
    <ol>
      <li><strong>Enter a known username or profile link.</strong> Use a handle you own or have permission to review in the <a href="/#tool=username">reverse username tool</a>.</li>
      <li><strong>Choose your scan scope:</strong> Start with a Quick scan (100 top platforms) or sign in for a Standard scan covering 560+ platforms.</li>
      <li><strong>Read each result label.</strong> Open candidate links and keep blocked, unavailable or ambiguous sources unresolved.</li>
      <li><strong>Verify leads at the source:</strong> Click the reported profile URLs to confirm account activity, creation dates, and public profile bios. Read our guide on <a href="/guides/verify-osint-account-matches.html">verifying OSINT account matches</a>.</li>
    </ol>
  </section>
  <section>
    <h2>Can you paste a profile link instead of a username?</h2>
    <p>The tool reads the handle from full profile URLs on Instagram, TikTok and GitHub. It removes share parameters from the source preview. For example, <code>instagram.com/example.name/?utm_source=share</code> becomes <code>example.name</code>. Formats like <code>tiktok.com/@example.name</code> and <code>github.com/example-name</code> also work.</p>
    <p>Use the address of the profile itself. Posts, videos, repositories and short links don’t identify a profile for this input. For other sites, type the handle shown on the profile. The preview shows the address you supplied and the handle the tool read from it. Review the result cards and verify candidates at their sources.</p>
  </section>
  <section>
    <h2 id="overcoming-false-positives-the-synthetic-control-advantage">Why a username result can be unconfirmed</h2>
    <p>A page can respond successfully while showing a generic page, a sign-in screen or an account-missing message. In <a href="/blog/username-search-benchmark-research.html#http-200-username-evidence">MyRecon's recorded checks</a>, one GitLab fixture returned HTTP 200 in 20 repeated observations where the official API found no account. Use the exact username and profile evidence at the source when reviewing a candidate.</p>
  </section>
  <section>
    <h2>How do you corroborate a username match?</h2>
    <p>Confirm your own account by signing in through its official site or app. For authorized review, look for links the owner published. Use multiple independent sources before assigning ownership.</p>
    <ul>
      <li><strong>Cross-linked bios:</strong> one profile links to the other, or both link to the same personal site or verified handle.</li>
      <li><strong>Copied images and similar display names:</strong> record these as clues and look for a source that verifies the connection.</li>
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
      <li><a href="/guides/reverse-gamertag-lookup.html">Reverse gamertag lookup for Xbox, PSN and Steam names</a></li>
      <li><a href="/guides/reddit-username-lookup.html">Reddit username lookup and account age</a></li>
      <li><a href="/guides/telegram-username-search.html">Telegram username search and collectible usernames</a></li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions</h2>
    <div class="faq">${lookupQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Ethical investigation guidelines</h2>
    <p>Reverse username lookups must be conducted responsibly. MyRecon queries publicly accessible endpoints and does not bypass private account settings or access restricted data. Use this tool for personal privacy audits, self-reconnaissance, and authorized security assessments. See our <a href="/terms.html">terms of use</a> and <a href="/privacy.html">privacy policy</a>.</p>
    <p>Access and evidence reviewed <time datetime="2026-11-27">27 November 2026</time>.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Reverse Username Search & Lookup (Free) | MyRecon',
  description: 'Run a free reverse username search and lookup across 100 sites as a guest or 560+ signed in. Paste a handle or profile URL and verify each lead.',
  url: `${site}/reverse-username-lookup.html`,
  outFileName: 'reverse-username-lookup.html',
  modifiedAt: '2026-11-27',
  crumbLabel: 'Reverse username lookup',
  questions: lookupQuestions,
  bodyHtml: lookupBody,
});

// 8. Reverse email lookup (24 Nov 2026). The Email tool already ran free for
// every visitor but had no page of its own; this is that page, with the
// lookup form first. Every claim below must match backend/services/email.py,
// modules/email_lookup.py and modules/registered_accounts.py.
const emailQuestions = [
  ['Is the reverse email lookup free?', 'Yes. Email lookups are free for every visitor and need no account. They do not use the username scan allowance, and MyRecon does not save the address to an account history.'],
  ['What does a reverse email lookup show?', 'Reported breaches that list the address and the data types each one exposed, plus public profiles tied to it such as Gravatar and GitHub commits. With linked-account checks on, it also shows registration signals from 100+ services. Each result names its source.'],
  ['Does the person who owns the email get notified?', 'Breach and public-profile checks do not contact the address. The optional linked-account checks send the address to each service they test, so a service could log the request. That is why the option is off by default.'],
  ['Can it tell me who owns an email address?', 'Not by itself. A public profile, a breach record or a registration signal is a lead about the address, not proof of identity. Confirm anything important with an independent source before you rely on it.'],
  ['Why does an address with no results still matter?', 'No result means the sources checked had nothing they could report. It does not prove the address was never breached or never used to sign up somewhere. Some services block automated checks, and those are shown as unresolved, not as clean.'],
];

const emailBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Reverse email lookup</span></nav>
  <h1>Reverse email lookup: find accounts and breaches linked to an email</h1>
  <p class="sub">Enter an email address to see the breaches that list it, the data each one exposed, and public profiles tied to it. Free, with no sign-in.</p>
  <username-search-input tool="email"></username-search-input>
  <p class="discovery-note">The lookup opens in the MyRecon tool and runs straight away. Nothing is saved to an account.</p>
  <section>
    <h2 id="what-the-lookup-checks">What the email lookup checks</h2>
    <dl>
      <dt><strong>Reported breaches</strong></dt>
      <dd>The address is checked against two free breach sources, LeakCheck and XposedOrNot. You see each named breach, its date where the source gives one, and the types of data it exposed, such as passwords, phone numbers or physical addresses. Large combined lists of old credentials are counted separately, so they do not inflate the number of distinct breaches.</dd>
      <dt><strong>Public profiles for the exact address</strong></dt>
      <dd>A public Gravatar profile and the accounts it lists, GitHub commits made with the address, and keys.openpgp.org, which only lists an address after its owner confirms it. These are things the owner of the address chose to publish.</dd>
      <dt><strong>Linked-account checks (optional)</strong></dt>
      <dd>Turn on "Also check linked accounts" and the lookup asks 100+ services, among them Spotify, Instagram, Pinterest, Amazon and Duolingo, whether the address is registered with them. This uses Holehe, an open-source tool, plus a few checks MyRecon maintains. It sends the address to every service it tests, so it is off unless you choose it.</dd>
    </dl>
    <p>Sensitive breaches, such as dating or adult sites that Have I Been Pwned marks as sensitive, are never listed against an address, and every result carries a note explaining that rule.</p>
  </section>
  <section>
    <h2 id="holehe-online">Holehe online, without installing Python</h2>
    <p>Holehe is an open-source command-line tool that checks whether an email address is registered on a service by reading how that service's sign-up or password-reset screen answers. Running it yourself means installing Python and the package, then reading raw output in a terminal.</p>
    <p>The linked-account option in this lookup runs a pinned copy of Holehe on MyRecon's server, plus two checks MyRecon maintains for Hugging Face and HackerRank, and shows the answers as a list: registered, no signal, or could not check. Rate limits and blocks are counted as "could not check", never as "not registered". As with Holehe itself, each service it tests receives the address.</p>
  </section>
  <section>
    <h2 id="google-reviews-by-email">Find Google reviews by email</h2>
    <p>Some people leave public Google Maps reviews under a contributor profile tied to their email address. <a href="/deep-search.html">Deep Search</a> takes an exact email, asks a public Google source for a contributor profile, and then collects the public Maps reviews for it: the place, rating, date, text and any owner reply that comes back.</p>
    <p>Guests can preview one finding; an eligible paid account unlocks the full results. Coverage can be partial or capped, and no profile or reviews does not prove that the address has no Google account or activity.</p>
  </section>
  <section>
    <h2 id="how-to-run-a-reverse-email-lookup">How to run a reverse email lookup</h2>
    <ol>
      <li><strong>Enter the address.</strong> Use one you own or have permission to review. Paste it exactly; the lookup checks that address only, not variations of it.</li>
      <li><strong>Decide on linked-account checks.</strong> Leave them off for a breach and public-profile check that contacts no one. Turn them on when you want registration signals and accept that each service sees the request.</li>
      <li><strong>Read the result in three parts.</strong> Breaches tell you what was exposed and when. Public profiles tell you what the owner published. Registration signals tell you where the address appears to have an account.</li>
      <li><strong>Act on it.</strong> Change any password that was reused on a breached service, turn on two-factor sign-in, and close accounts you no longer use. The <a href="/guides/check-email-data-breach.html">email breach guide</a> walks through each step.</li>
    </ol>
  </section>
  <section>
    <h2 id="reading-registration-signals">How to read a registration signal</h2>
    <p>A registration check looks at how a service answers when asked about an address, usually on its sign-up or password-reset screen. If the answer differs for a registered address, that difference is the signal. It is good evidence that an account exists. It is not proof of who controls the account today.</p>
    <p>Services change these screens without notice, and many rate-limit or block automated requests. MyRecon reports those as unresolved and counts them, so a partial run never reads as "no accounts". A service that is missing from the results means the lookup found no evidence there, not that no account exists.</p>
  </section>
  <section>
    <h2 id="breach-results">What a breach result means for you</h2>
    <p>A breach entry means the address appeared in data that a service lost or that was later traded. The exposed data types matter more than the count. A breach that included passwords means any password you used on that service, and anywhere you reused it, should be treated as known. A breach that included phone numbers raises the risk of SIM-swap and text-message scams.</p>
    <p>Breach dates are when the incident happened according to the source, which is often months before it was disclosed. For background on a specific incident, open the <a href="/breaches/">breach archive</a>, which explains individual breaches from their published records.</p>
  </section>
  <section>
    <h2 id="email-lookup-compared">How this compares with other email lookup tools</h2>
    <p>Holehe is the open-source command-line tool behind the linked-account checks; running it yourself needs Python and gives you the raw answers. Have I Been Pwned is the reference for breach notifications and offers its own alerts. MyRecon puts breach data, public profiles and registration signals in one browser lookup and labels what it could not check. See the <a href="/blog/best-email-osint-tools.html">email OSINT tools comparison</a> and the <a href="/blog/best-data-breach-checkers.html">breach checker comparison</a> for more options.</p>
  </section>
  <section>
    <h2 id="related-tools">Related tools</h2>
    <ul>
      <li><a href="/reverse-username-lookup.html">Reverse username lookup</a> for a handle that appears in your results</li>
      <li><a href="/digital-footprint-checker.html">Digital footprint checker</a> for a combined email and username audit</li>
      <li><a href="/#tool=password">Password exposure check</a>, which never sends the password itself</li>
      <li><a href="/guides/spf-dkim-dmarc-explained.html">SPF, DKIM and DMARC explained</a> if the address is on a domain you run</li>
    </ul>
  </section>
  <section>
    <h2>Frequently asked questions</h2>
    <div class="faq">${emailQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>
  <section>
    <h2>Using email lookups responsibly</h2>
    <p>Look up your own addresses, or addresses you are authorized to review for security work. Do not use the results to harass, track or impersonate anyone. Read the <a href="/terms.html">terms of use</a> and the <a href="/privacy.html">privacy policy</a>.</p>
    <p>Sources and behaviour reviewed <time datetime="2026-11-27">27 November 2026</time>.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Free Reverse Email Lookup: Accounts & Breaches | MyRecon',
  description: 'Look up an email address free, with no sign-in. See breaches that list it, the data they exposed, public profiles, and optional linked-account checks.',
  url: `${site}/reverse-email-lookup.html`,
  outFileName: 'reverse-email-lookup.html',
  modifiedAt: '2026-11-27',
  crumbLabel: 'Reverse email lookup',
  questions: emailQuestions,
  bodyHtml: emailBody,
  webApplication: {
    '@type': 'WebApplication',
    name: 'MyRecon reverse email lookup',
    url: `${site}/reverse-email-lookup.html`,
    applicationCategory: 'SecurityApplication',
    operatingSystem: 'Any',
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  },
});

// 9. Discord ID lookup (added 2026-11-28). "discord id lookup" is 10K-100K
// searches a month worldwide in Keyword Planner (28 Nov 2026), low competition,
// and the results are single-purpose tools. Everything is decoded in the
// browser by assets/js/discord-id-lookup.js. The public name, avatar and
// badges come from /api/discord/user/<id> (backend/services/discord_lookup.py),
// which needs DISCORD_BOT_TOKEN on Render. Never claim anything private.
const discordQuestions = [
  ['Can I find a Discord user by ID?', 'Yes, for the public profile. Paste a user ID and the lookup shows the current username, display name, avatar, banner and public badges that Discord returns for that ID, plus the creation date decoded from the number. It cannot show an email address, phone number, IP address or location, because Discord does not give those out.'],
  ['How do I tell how old a Discord account is?', 'Copy the user ID with Developer Mode switched on and paste it into the lookup. The first 42 bits of the ID are the creation time, so the result is exact to the millisecond and the account cannot change it.'],
  ['Does a Discord ID ever change?', 'No. Usernames, display names, server nicknames and avatars can all change, but the ID stays the same for the life of the account, server, channel or message.'],
  ['Is it safe to share a Discord ID?', 'An ID on its own reveals only a creation date. Share it with Discord or a server moderator when you report someone, but avoid posting it publicly next to private messages or personal details.'],
  ['Can this tool see deleted accounts or private servers?', 'It decodes the number you paste and nothing else. It cannot tell whether an account still exists, was deleted or banned, or what a private server contains.'],
];

const discordBody = `<main id="main" class="container prose discovery-page">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">MyRecon</a> / <span aria-current="page">Discord ID lookup</span></nav>
  <h1>Discord ID lookup: decode any user, server or message ID</h1>
  <p class="sub">Paste a Discord ID, a mention such as &lt;@175928847299117063&gt;, or a message link. You get the exact creation date, the account age, timestamp codes you can paste into Discord and, for user IDs, the public name and avatar. The date is decoded in your browser; for the profile, only the ID is sent to MyRecon, which asks Discord.</p>
  <form id="discord-lookup-form" class="discord-lookup" autocomplete="off">
    <label for="discord-lookup-input">Discord ID, mention or link</label>
    <input id="discord-lookup-input" inputmode="text" spellcheck="false" placeholder="175928847299117063">
    <details class="discord-compare-toggle">
      <summary>Compare with a second ID (spot a newer copycat account)</summary>
      <label for="discord-lookup-compare">Second Discord ID</label>
      <input id="discord-lookup-compare" inputmode="text" spellcheck="false" placeholder="Another user ID">
    </details>
    <button type="submit" class="btn btn-primary">Look up ID</button>
  </form>
  <div id="discord-lookup-result" aria-live="polite"></div>
  <p class="discovery-note">Try Discord's own documented example, 175928847299117063. It decodes to 30 April 2016, 11:18:25.796 UTC.</p>

  <section>
    <h2>What a Discord ID lookup shows</h2>
    <ul>
      <li><strong>Public profile.</strong> Current username, display name, avatar, banner and public badges, as Discord returns them for a user ID.</li>
      <li><strong>Creation date and time.</strong> Exact to the millisecond, in UTC and in your own time zone.</li>
      <li><strong>Account age.</strong> How many years, months and days ago the account, server, channel or message was created.</li>
      <li><strong>Timestamp codes.</strong> All nine &lt;t:unix:style&gt; formats, ready to copy into a Discord message.</li>
      <li><strong>Default avatar.</strong> Which of Discord's six default avatars a user on the new username system gets if they have not uploaded a picture.</li>
      <li><strong>Which of two accounts is older.</strong> Paste a second ID to compare, which is the quickest check against an impersonator.</li>
    </ul>
    <p>It does not show an email address, phone number, IP address, location or server list. None of those are in the ID, and Discord's API does not give them to anyone looking up a user. A site that promises them from an ID alone is not telling the truth.</p>
    <p>The profile is fetched with Discord's documented "Get User" request through a MyRecon bot account. If Discord says no user has that ID, the number is a server, channel or message ID, or the account was deleted.</p>
  </section>

  <section>
    <h2>What you can paste</h2>
    <p>The lookup reads the ID out of the common forms people copy from Discord:</p>
    <ul>
      <li>A bare ID, 17 to 20 digits for anything created in recent years.</li>
      <li>A user mention, <code>&lt;@ID&gt;</code>, or the older <code>&lt;@!ID&gt;</code> form.</li>
      <li>A role <code>&lt;@&amp;ID&gt;</code>, channel <code>&lt;#ID&gt;</code> or custom emoji <code>&lt;:name:ID&gt;</code>.</li>
      <li>A message link, <code>discord.com/channels/server/channel/message</code>. The server, channel and message are decoded separately.</li>
      <li>A profile link, <code>discord.com/users/ID</code>.</li>
    </ul>
    <p>To copy an ID inside Discord, switch on Developer Mode in the app's Advanced settings, then use Copy User ID, Copy Server ID or Copy Message Link from the right-click or long-press menu. The <a href="/guides/discord-id-creation-date.html">Discord ID creation date guide</a> walks through the menus on desktop and mobile.</p>
  </section>

  <section>
    <h2>How the date is worked out</h2>
    <p>Discord IDs are 64-bit "snowflakes". Discord's developer reference documents the layout: bits 63 to 22 hold milliseconds since the Discord epoch, 1420070400000 (the first second of 2015), and the low 22 bits hold an internal worker ID, process ID and counter. The creation time is <code>(id &gt;&gt; 22) + 1420070400000</code>.</p>
    <p>The tool does that shift with JavaScript's BigInt. Ordinary numbers in a spreadsheet or in JavaScript lose the last digits of an 18-digit integer, which is why some quick converters are off by a few seconds.</p>
  </section>

  <section>
    <h2>Using account age to check an impersonator</h2>
    <p>Copycat accounts take a real person's name and picture, then message their friends or community. They cannot copy the ID. Put the real account's ID in the first box and the suspicious one in the second: if the real account dates from 2019 and the other from last Tuesday, you have your answer, and the ages go straight into your report to the server's moderators or to Discord.</p>
    <p>Age is a signal, not proof. An old account can be stolen and a new one can be genuine, for example when someone has just lost access to their old login. For a full method, see <a href="/guides/identify-impersonation-accounts">how to identify impersonation accounts</a> and <a href="/blog/report-social-media-impersonation.html">how to report impersonation</a>.</p>
  </section>

  <section>
    <h2>Discord timestamp codes</h2>
    <p>Discord turns <code>&lt;t:UNIX:STYLE&gt;</code> into a date shown in each reader's own time zone. The Unix time is in seconds. Styles from Discord's message formatting reference:</p>
    <div class="discovery-table-wrap" tabindex="0" role="region" aria-label="Discord timestamp styles">
    <table>
      <caption>Timestamp styles as listed by Discord</caption>
      <thead><tr><th>Style</th><th>Example display</th></tr></thead>
      <tbody>
        <tr><td><code>t</code></td><td>16:20</td></tr>
        <tr><td><code>T</code></td><td>16:20:30</td></tr>
        <tr><td><code>d</code></td><td>20/04/2021</td></tr>
        <tr><td><code>D</code></td><td>April 20, 2021</td></tr>
        <tr><td><code>f</code> (default)</td><td>April 20, 2021 at 16:20</td></tr>
        <tr><td><code>F</code></td><td>Tuesday, April 20, 2021 at 16:20</td></tr>
        <tr><td><code>s</code></td><td>20/04/2021, 16:20</td></tr>
        <tr><td><code>S</code></td><td>20/04/2021, 16:20:30</td></tr>
        <tr><td><code>R</code></td><td>4 years ago</td></tr>
      </tbody>
    </table>
    </div>
  </section>

  <section>
    <h2>Looking for a person rather than an ID?</h2>
    <p>If you know a handle rather than a number, a <a href="/reverse-username-lookup.html">reverse username lookup</a> checks where the same name appears across 560+ public platforms. Discord does not publish user profiles to the open web, so the <a href="/find/discord-user">Discord user lookup page</a> explains what can and cannot be found from a username.</p>
  </section>

  <section>
    <h2>Discord ID lookup questions</h2>
    <div class="faq">${discordQuestions.map(([q, a]) => `<details><summary>${q}</summary><p>${a}</p></details>`).join('')}</div>
  </section>

  <section>
    <h2>Sources</h2>
    <p>Snowflake layout, Discord epoch, mention formats, timestamp styles and the default avatar rule: Discord developer documentation, Reference ("Snowflakes", "Message Formatting", "Image Formatting"). Profile fields and badge names: Discord developer documentation, Users ("Get User", "User Flags"). Both read 28 November 2026. Updated 28 November 2026.</p>
  </section>
</main>`;

buildDiscoveryPage({
  title: 'Discord ID Lookup: Profile, Avatar & Account Age | MyRecon',
  description: 'Free Discord ID lookup. Paste a user, server or message ID to see the public profile, avatar and badges, the creation date and the account age.',
  url: `${site}/discord-id-lookup.html`,
  outFileName: 'discord-id-lookup.html',
  modifiedAt: '2026-11-28',
  crumbLabel: 'Discord ID lookup',
  questions: discordQuestions,
  bodyHtml: discordBody,
  webApplication: {
    '@type': 'WebApplication',
    name: 'MyRecon Discord ID lookup',
    url: `${site}/discord-id-lookup.html`,
    applicationCategory: 'UtilitiesApplication',
    operatingSystem: 'Any',
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  },
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
