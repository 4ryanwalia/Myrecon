/* Page-specific Android promotion, applied after all page generators. */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const play = 'https://play.google.com/store/apps/details?id=com.Myrecon.osint&amp;referrer=utm_source%3Dmyrecon.xyz%26utm_medium%3Dwebsite%26utm_campaign%3Dandroid_promotion';
function promotionFor(route) {
  const variants = {
    breach: { tag: 'BREACH ALERTS + STORIES', title: 'Big breaches.<br>The story behind them.', text: 'Turn on daily breach stories and alerts for newly reported breaches. Watch your email for new exposure that could affect you.', features: ['Daily stories', 'Breach alerts', 'Email watch'], note: 'Enable alerts in the app. Coverage and delivery vary.' },
    cases: { tag: 'READ THE FULL STORY', title: 'Real breaches.<br>Stories worth reading.', text: 'Discover how major breaches happened, what was exposed and what came next. Turn on a daily story and breach alerts in the app.', features: ['Case files', 'Daily stories', 'Breach alerts'], note: 'Story reminders and security alerts are separate opt-ins.' },
    research: { tag: 'DEEP SEARCH INCLUDED', title: 'From reading.<br>To discovering.', text: 'Put the guide into practice. Explore public usernames, follow profile leads and try Deep Search from your Android phone.', features: ['Deep Search', 'Username search', 'Breach checks'], note: 'Use for your own accounts or authorized research.' },
    privacy: { tag: 'YOUR PRIVACY, IN YOUR HANDS', title: 'Know your footprint.<br>Take the next step.', text: 'Find public profile leads, check supported email breach records and review your device’s privacy settings in one app.', features: ['Footprint checks', 'Email exposure', 'Device privacy'], note: 'App checks are separate from our managed removal service.' },
    compare: { tag: 'TRY THE TOOLS YOURSELF', title: 'Compare less.<br>Explore more.', text: 'See how MyRecon fits your research. Try username search, breach checks and Deep Search together on Android.', features: ['Deep Search', 'Public profiles', 'Breach checks'], note: 'Results depend on public-source availability.' },
    technical: { tag: 'TOOLS THAT TRAVEL WITH YOU', title: 'A closer look.<br>Wherever you are.', text: 'Explore domain and DNS information, review device privacy and follow public profile leads from your phone.', features: ['Domain + DNS', 'Device privacy', 'Deep Search'], note: 'Research infrastructure you own or have permission to check.' },
    general: { tag: 'DEEP SEARCH INCLUDED', title: 'Your next discovery.<br>On your phone.', text: 'Take MyRecon with you. Search public usernames, explore breach stories and check your digital footprint on Android.', features: ['Deep Search', 'Username search', 'Breach stories'], note: '' }
  };
  let key = 'general';
  if (/case-files/.test(route)) key = 'cases';
  else if (/breach|incident/.test(route)) key = 'breach';
  else if (/privacy|footprint|services|delete|deactivat|doxx|impersonat/.test(route)) key = 'privacy';
  else if (/^vs\/|compar|pricing/.test(route)) key = 'compare';
  else if (/dns|domain|whois|ip-/.test(route)) key = 'technical';
  else if (/^blog\/|^guides\/|^find\/|username|osint|search/.test(route)) key = 'research';
  const copy = variants[key];
  return `<aside class="android-promo" aria-label="MyRecon Android limited-time offer"><div class="promo-art" aria-hidden="true"><span class="promo-art-orbit"></span><svg viewBox="0 0 180 140" fill="none"><rect x="57" y="7" width="70" height="126" rx="15" fill="var(--surface)" stroke="currentColor" stroke-width="2"/><path d="M81 17h22M84 122h16" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="91" cy="65" r="22" stroke="currentColor" stroke-width="2"/><circle cx="91" cy="65" r="10" stroke="currentColor" stroke-width="2"/><path d="m107 81 13 13M91 36v8M62 65h8M112 65h8M91 86v8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><span class="promo-art-tag">${copy.tag}</span></div><div class="promo-copy"><span class="android-promo-label">MYRECON FOR ANDROID</span><span class="promo-offer">Free for a limited time</span><h2>${copy.title}</h2><p>${copy.text}</p><p class="promo-free"><strong>Everything in the app is free for a limited time. Deep Search included.</strong></p><ul class="promo-features">${copy.features.map(feature => `<li>${feature}</li>`).join('')}</ul><a class="android-promo-link" href="${play}">Download free now <span aria-hidden="true">↗</span></a><small>Android only for now. Sorry, fellow iOS users!<br>Google Play · Android 11+ · Contains ads${copy.note ? `<br>${copy.note}` : ''}</small></div></aside>`;
}
let pages = 0;
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.') || ['node_modules', 'content', 'scripts', 'tests', 'data', 'worker-console', 'assets'].includes(entry.name)) continue;
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) { walk(file); continue; }
    if (!entry.name.endsWith('.html')) continue;
    let html = fs.readFileSync(file, 'utf8');
    const rel = path.relative(root, file).replace(/\\/g, '/');
    if (!/<main\b/.test(html) || /<meta[^>]+name="robots"[^>]+content="[^"]*noindex/i.test(html)) continue;
    const article = /"@type"\s*:\s*"(?:Article|BlogPosting|NewsArticle)"/.test(html) || /<main\b[^>]*class="[^"]*seo-page/.test(html);

    const banner = promotionFor(rel);
    html = html.replace(/<aside class="android-promo"[\s\S]*?<\/aside>/g, '');
    // Remove our previous layout before rebuilding: exactly one promotion per page.
    html = html.replace(/<!-- app-promo-layout:start --><div class="promo-layout">/g, '').replace(/<div class="promo-rail">\s*<\/div><\/div><!-- app-promo-layout:end -->/g, '');
    // The pricing page keeps checkout in focus: no Android promotion there.
    if (rel === 'pricing.html') {
      html = html.replace(/<link rel="stylesheet" href="\/assets\/(?:optimized\/)?css\/android-promo[^"]*\.css">\r?\n?/g, '');
      fs.writeFileSync(file, html.replace(/[ \t]+$/gm, ''));
      continue;
    }
    if (rel === 'index.html') {
      html = html.replace('</main>', `${banner}\n</main>`);
    } else {
      html = html.replace(/<main\b/, '<!-- app-promo-layout:start --><div class="promo-layout"><main');
      html = html.replace('</main>', `</main><div class="promo-rail">${banner}</div></div><!-- app-promo-layout:end -->`);
    }
    if (!/\/assets\/(?:optimized\/)?css\/android-promo[.]/.test(html)) html = html.replace('</head>', '<link rel="stylesheet" href="/assets/css/android-promo.css">\n</head>');
    fs.writeFileSync(file, html.replace(/[ \t]+$/gm, ''));
    pages++;
  }
}
walk(root);
console.log(`[promotion] ${pages} pages with Android banners`);
