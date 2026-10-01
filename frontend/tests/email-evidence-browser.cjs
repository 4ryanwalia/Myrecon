/* Offline email journey: real page, synthetic provider findings, no external calls. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.resolve(root, '../output/email-evidence');
fs.mkdirSync(out, { recursive: true });
const checked = { checked: true, status: 'ok', breached: true };
const data = { status: 'ok', query: { email: 'fixture@example.com' },
  analysis: { provider: 'Example mail', provider_type: 'custom', deliverable: true, disposable: false, mx_hosts: ['mx.example.com'] },
  summary: { breached: true, breach_count: 2, breach_status: 'ok', records_found: 5 },
  breaches: { ...checked, sources: [{ name: 'Canva', date: '2019' }, { name: 'Example incident' }], fields: ['email', 'password'] },
  darkweb: { ...checked, breaches: [{ name: 'Canva', date: '2019', exposed: ['Email addresses', 'Passwords'] }] }, fallback: { status: 'skipped' },
  account_checks: { enabled: true, sources: [{ name: 'GitHub', status: 'found' }, { name: 'Gravatar', status: 'found' }] },
  registration_checks: { status: 'ok', checked: 2, attempted: 3, catalogue_count: 123, services: [{ service: 'Spotify', status: 'found', reason: 'Service registration signal' }, { service: 'Other', status: 'timeout', reason: 'Provider timeout' }] },
  linked_services: { services: [{ service: 'Canva', kind: 'breach', date: '2019', evidence: 'Historical association' }, { service: 'Spotify', kind: 'registration', evidence: 'Service signal' }] },
  evidence_report: { version: 1, counts: { public_profiles: 2, registration_signals: 1, historical_services: 1, named_breaches: 2 },
    identity: { display_name: [{ value: 'Example Developer', source: 'GitHub', basis: 'historical_commit' }, { value: 'Example Dev', source: 'Gravatar', basis: 'email_hash' }], username: [{ value: 'example-dev', source: 'GitHub', basis: 'historical_commit' }], location: [{ value: 'Self-reported city', source: 'GitHub', basis: 'historical_commit' }] },
    earliest: { date_label: '2019' }, latest: { date_label: 'Sep 1, 2020' },
    date_note: 'Earliest and latest refer only to dated evidence returned by these sources. They are not first or last use of this email.',
    identity_note: 'Names and locations are source-reported profile fields. They do not establish that all profiles belong to one person or where someone currently lives.',
    profiles: [{ platform: 'GitHub', username: 'example-dev', display_name: 'Example Developer', url: 'https://github.com/example-dev', bio: 'A synthetic public profile for layout testing.', location: 'Self-reported city', company: 'Example company', website: 'https://example.com', stats: { 'Public repositories': 12, Followers: 0 }, basis: 'historical_commit', source: 'GitHub public API', evidence: 'Public commit with this exact author email; current account email is unknown.', evidence_url: 'https://github.com/example-dev/repo/commit/1', profile_status: 'ok' },
      { platform: 'Gravatar', display_name: 'Example Dev', url: 'https://gravatar.com/example', bio: 'Public profile fixture.', source: 'Gravatar public profile', evidence: 'Profile for the email hash', basis: 'email_hash', stats: {}, profile_status: 'ok' }],
    timeline: [{ kind: 'activity', title: 'Public GitHub commit', date: '2020-09-01', date_label: 'Sep 1, 2020', precision: 'day', sources: ['GitHub commit search'], detail: 'Author-supplied commit date; current ownership is not established.', url: 'https://github.com/example-dev/repo/commit/1' },
      { kind: 'profile', title: 'GitHub profile created', date: '2020-01-01', date_label: 'Jan 1, 2020', precision: 'day', sources: ['GitHub public API'], detail: 'Creation of this profile, not its email association.', url: 'https://github.com/example-dev' },
      { kind: 'breach', title: 'Canva breach', date: '2019', date_label: '2019', precision: 'year', sources: ['XposedOrNot analytics', 'LeakCheck'], detail: 'Reported breach date, not when this email was first seen.', url: '' }],
    undated_events: [{ kind: 'breach', title: 'Example incident breach', date: '', date_label: 'Date not provided', precision: 'unknown', sources: ['LeakCheck'], detail: 'No date was supplied.', url: '' }] },
};
data.darkweb.exposed_data = [{ name: 'Passwords', count: 1 }];
const reviews = Array.from({ length: 8 }, (_, n) => ({ name: `Example venue ${n + 1}`, address: `Example street ${n + 1}`, rating: n ? 5 : 4.5, text: n ? 'Synthetic review for testing.' : '', date_label: '3 weeks ago', latitude: 10 + n, longitude: 20 + n, owner_reply: 'Synthetic owner reply.', owner_reply_date: '2 weeks ago', source_url: 'https://example.com/review' }));
data.evidence_report.profiles.push({ platform: 'Google', display_name: 'Example User', fields: { ID: '123456789', 'Enterprise user': 'No' }, lists: { 'Active Google apps': ['Maps', 'Photos'] }, stats: { Reviews: 5, Ratings: 3, Answers: 11 }, reviews, source: 'Test provider', basis: 'provider_email', last_seen: '2024-09-01', evidence: 'Synthetic source association.' },
  { platform: 'LinkedIn', display_name: 'Example User', bio: 'Synthetic professional profile.', location: 'Declared city', fields: { Connections: '500' }, positions: [{ title: 'Engineer', company: 'Example company', current: true, start: '2023-12' }, { title: 'Consultant', company: 'Example company', start: '2022-04', end: '2023-04' }], education: [{ school: 'Example university', start: '2016', end: '2020' }], source: 'Test provider', basis: 'provider_email', evidence: 'Synthetic source association.' });
data.evidence_report.counts.public_profiles = 4;
data.evidence_report.locations = reviews.map(r => ({ value: r.address, source: 'Google', basis: 'review_venue', date_label: r.date_label, url: `https://www.google.com/maps?q=${r.latitude},${r.longitude}` }));
data.evidence_report.registrations = [{ service: 'Spotify', source: 'Test provider', reason: 'Synthetic registration signal' }];
let response = data;
let requestBody;
let photoRequests = 0;
let usernameRequests = 0;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (pathname.startsWith('/api/username')) { usernameRequests++; res.statusCode = 500; return res.end(); }
  if (pathname === '/fixture-avatar.svg') {
    res.setHeader('Content-Type', 'image/svg+xml'); return res.end('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" rx="40" fill="#435365"/><text x="40" y="50" text-anchor="middle" font-family="sans-serif" font-size="28" fill="white">E</text></svg>');
  }
  if (pathname === '/api/email/photo') {
    photoRequests++;
    const upstream = new URL(req.url, 'http://localhost').searchParams.get('url');
    if (upstream.includes('fixture-unavailable')) { res.statusCode = 404; return res.end(); }
    res.setHeader('Content-Type', 'image/png');
    return res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==', 'base64'));
  }
  if (pathname === '/api/email') {
    let body = ''; req.on('data', (chunk) => { body += chunk; }); req.on('end', () => {
      requestBody = JSON.parse(body); res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(response));
    }); return;
  }
  if (pathname === '/assets/js/account.js') {
    res.setHeader('Content-Type', 'application/javascript'); return res.end('window.MyReconAccount={enabled:false,ready:Promise.resolve(),state:()=>({user:null}),onChange:()=>{},authHeaders:async()=>({})};');
  }
  if (pathname === '/assets/js/config.js') {
    res.setHeader('Content-Type', 'application/javascript'); return res.end('window.MYRECON_API_BASE=location.origin;\n' + fs.readFileSync(path.join(root, 'assets/js/config.js'), 'utf8'));
  }
  const file = path.resolve(root, '.' + pathname);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode = 404; return res.end(); }
  res.setHeader('Content-Type', ({ '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json' })[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  data.evidence_report.profiles.forEach(p => { p.avatar_url = base + '/fixture-avatar.svg?platform=' + encodeURIComponent(p.platform); });
  const browser = await chromium.launch({ executablePath: process.env.MYRECON_BROWSER || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
    const errors = []; page.on('pageerror', (e) => errors.push(e.message));
    await page.route('**/*', (route) => route.request().url().startsWith(base) ? route.continue() : route.abort());
    await page.goto(base + '/index.html#tool=email');
    await page.locator('#queryInput').fill('fixture@example.com');
    await page.locator('#linkedAccountsToggle').check();
    await page.locator('#runBtn').click();
    await page.locator('.email-overview').waitFor();
    assert.equal(requestBody.check_linked_accounts, true);
    assert.equal(await page.locator('.email-evidence-counts strong').allTextContents().then(v => v.join(',')), '4,1,1,2');
    assert.equal(await page.locator('.email-profile-card').count(), 4);
    assert.equal(await page.locator('.email-review').count(), 8);
    assert.equal(await page.locator('.email-career').count(), 3);
    await page.waitForFunction(() => [...document.querySelectorAll('.email-photo-strip img')].length === 4 && [...document.querySelectorAll('.email-photo-strip img')].every(img => img.complete && img.naturalWidth > 0));
    assert.equal(await page.getByText('What leaked about this address', { exact: true }).count(), 0);
    assert.equal(await page.getByText('Address analysis', { exact: true }).count(), 0);
    assert.equal(await page.getByText('Email infrastructure', { exact: true }).count(), 0);
    await page.locator('.email-locations summary').click();
    assert.equal(await page.getByRole('link', { name: 'Example street 8 ↗', exact: true }).isVisible(), true);
    assert.equal(await page.locator('.email-review a').first().getAttribute('href'), 'https://www.google.com/maps?q=10,20');
    await page.locator('[data-kind="breach"]').click();
    assert.equal(await page.locator('.email-evidence-timeline > .email-event-list > li:visible').count(), 1);
    await page.locator('[data-kind="all"]').click();
    assert.equal(await page.locator('.email-evidence-timeline > .email-event-list > li:visible').count(), 3);
    await page.locator('.email-undated summary').click();
    assert.equal(await page.getByText('Example incident breach', { exact: true }).isVisible(), true);
    await page.screenshot({ path: path.join(out, 'desktop-dark.png'), fullPage: true });
    await page.locator('.email-overview').screenshot({ path: path.join(out, 'overview-dark.png'), style: '.nav, .toast, .toasts { visibility: hidden; }' });
    await page.locator('.email-platform-summary').screenshot({ path: path.join(out, 'platform-summary-dark.png'), style: '.nav, .toast, .toasts { visibility: hidden; }' });
    await page.locator('.email-review').first().screenshot({ path: path.join(out, 'review-card-dark.png'), style: '.nav, .toast, .toasts { visibility: hidden; }' });
    await page.locator('.email-evidence-timeline').screenshot({ path: path.join(out, 'timeline-dark.png'), style: '.nav, .toast { visibility: hidden; }' });
    await page.locator('.email-profile-card').nth(2).screenshot({ path: path.join(out, 'google-reviews-dark.png'), style: '.nav, .toast { visibility: hidden; }' });
    await page.locator('.email-profile-card').nth(3).screenshot({ path: path.join(out, 'linkedin-dark.png'), style: '.nav, .toast { visibility: hidden; }' });
    await page.evaluate(() => { window.print = () => { window.testPrintCalled = true; }; });
    await page.locator('[data-action="print"]').click();
    assert.equal(await page.evaluate(() => window.testPrintCalled), true);
    if (!process.env.MYRECON_SKIP_PDF) await page.pdf({ path: path.join(out, 'fixture-report.pdf'), format: 'A4', printBackground: true });
    const downloadPromise = page.waitForEvent('download');
    await page.locator('[data-export="json"]').click();
    const download = await downloadPromise;
    await download.saveAs(path.join(out, 'fixture-report.json'));
    const exported = JSON.parse(fs.readFileSync(path.join(out, 'fixture-report.json'), 'utf8'));
    assert.equal(exported.evidence_report.timeline.length, 3);
    assert.equal(exported.summary.coverage_incomplete, false);
    await page.locator('#themeToggle').click();
    await page.locator('.email-overview').screenshot({ path: path.join(out, 'overview-light.png'), style: '.nav, .toast { visibility: hidden; }' });
    await page.locator('.email-profile-card').nth(2).screenshot({ path: path.join(out, 'google-reviews-light.png'), style: '.nav, .toast, .toasts { visibility: hidden; }' });
    for (const width of [375, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'overflow at ' + width);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(out, 'mobile-light.png'), fullPage: true });
    await page.locator('.email-profile-card').nth(2).screenshot({ path: path.join(out, 'google-reviews-mobile.png'), style: '.nav, .toast, .toasts { visibility: hidden; }' });
    await page.locator('.email-overview').screenshot({ path: path.join(out, 'overview-mobile.png'), style: '.nav, .toast { visibility: hidden; }' });
    await page.locator('#themeToggle').click();
    await page.locator('.email-evidence-timeline').screenshot({ path: path.join(out, 'timeline-mobile.png'), style: '.nav, .toast { visibility: hidden; }' });
    // A reported handle opens the existing scanner without starting requests.
    const searchUsername = page.getByRole('button', { name: 'Search this username: example-dev', exact: true });
    assert.equal(await searchUsername.count(), 1);
    await searchUsername.click();
    assert.equal(await page.locator('#tab-username').getAttribute('aria-selected'), 'true');
    assert.equal(await page.locator('#queryInput').inputValue(), 'example-dev');
    assert.match(await page.locator('#panelSub').textContent(), /do not verify the same person/);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(usernameRequests, 0, 'prefilling must never run a username scan');
    await page.locator('#tab-email').click();
    await page.locator('#queryInput').fill('fixture@example.com');
    // Exercise real browser image errors: retry a public CDN once, then keep
    // useful initials for an unavailable/private image without a broken glyph.
    response = JSON.parse(JSON.stringify(data));
    response.evidence_report.profiles[2].avatar_url = 'https://lh3.googleusercontent.com/fixture-retry';
    response.evidence_report.profiles[3].avatar_url = 'https://media.licdn.com/fixture-unavailable';
    await page.locator('#runBtn').click();
    await page.waitForFunction(() => document.querySelectorAll('.email-photo-strip .avatar.loaded').length === 3 && document.querySelectorAll('.email-photo-strip .avatar[title="Photo unavailable"]').length === 1);
    assert.equal(await page.locator('.email-photo-strip img').count(), 3);
    assert.equal(await page.locator('.email-photo-strip figure').nth(3).textContent(), 'LiLinkedIn');
    assert.ok(photoRequests >= 2 && photoRequests <= 4, 'at most one retry per rendered photo');
    assert.equal(await page.locator('.email-profile-card').nth(3).locator('.avatar .avatar-fallback').isVisible(), true);
    response = { ...data, breaches: { status: 'unavailable', checked: false }, darkweb: { status: 'unavailable', checked: false }, linked_services: { services: [] }, registration_checks: { status: 'skipped', services: [] }, account_checks: { enabled: false, sources: [] },
      summary: { breached: false, breach_status: 'unavailable', breach_count: 0 }, evidence_report: { version: 1, counts: {}, identity: {}, profiles: [], timeline: [], undated_events: [], date_note: data.evidence_report.date_note, identity_note: data.evidence_report.identity_note } };
    await page.locator('#linkedAccountsToggle').uncheck();
    await page.locator('#runBtn').click();
    await page.getByText('No usable dates were returned. Undated findings are still shown below.', { exact: true }).waitFor();
    assert.equal(requestBody.check_linked_accounts, false);
    assert.equal(await page.locator('[data-action="retry-email"]').isVisible(), true);
    assert.equal(await page.locator('.email-profile-card').count(), 0);
    assert.equal(await page.locator('.email-evidence-range').textContent().then(t => t.includes('Not available')), true);
    assert.deepEqual(errors, []);
    console.log('Email browser checks passed: filters, export, explicit username follow-up, photo retry/fallback, removed infrastructure, opt-in, outages, dark/light and 375/390/768px layouts.');
  } finally { await browser.close(); server.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; server.close(); });
