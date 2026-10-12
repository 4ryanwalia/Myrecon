const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const site = 'https://www.myrecon.xyz';
const config = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json')));
function fileFor(route) {
  const file = path.join(root, route.slice(1));
  return route.endsWith('/') ? path.join(file, 'index.html') : fs.existsSync(file) ? file : `${file}.html`;
}
test('every sitemap URL is discoverable by following links from the homepage', () => {
  const urls = [...fs.readFileSync(path.join(root, 'sitemap.xml'), 'utf8').matchAll(/<loc>(.*?)<\/loc>/g)].map(m => new URL(m[1]).pathname);
  const reached = new Set(), queue = ['/'];
  while (queue.length) {
    let route = queue.shift();
    route = config.redirects.find(r => r.source === route)?.destination || route;
    if (reached.has(route)) continue;
    reached.add(route);
    const file = fileFor(route);
    if (!fs.existsSync(file) || !file.endsWith('.html')) continue;
    const html = fs.readFileSync(file, 'utf8');
    for (const [, href] of html.matchAll(/href=["']([^"']+)["']/g)) {
      const url = new URL(href, site + route);
      if (url.origin !== site || /\.(css|js|svg|png|json|csv|xml|ico|webp|jpg|txt)$/.test(url.pathname)) continue;
      const target = fileFor(url.pathname);
      if (fs.existsSync(target) && target.endsWith('.html')) {
        const document = fs.readFileSync(target, 'utf8');
        const canonical = document.match(/rel="canonical" href="([^"]+)"/);
        queue.push(canonical ? new URL(canonical[1]).pathname : url.pathname);
      } else queue.push(url.pathname);
    }
  }
  assert.deepEqual(urls.filter(url => !reached.has(url)), []);
});
test('historical worked example agrees with its preserved raw evidence', () => {
  const data = JSON.parse(fs.readFileSync(path.join(root, 'assets/data/benchmark-observation-2026-10-02.json')));
  const row = data.run.checks.find(c => c.username === 'torvalds' && c.platform === 'GitLab');
  assert.equal(row.reference.status_code, 200);
  assert.equal(row.reference.verdict, 'not_found');
  assert.equal(row.http200_baseline.verdict, 'found');
  assert.equal(data.run.tools.http200_baseline.unknown, 16);
  assert.match(data.methodology.reference, /shares some API evidence/);
  const html = fs.readFileSync(path.join(root, 'guides/account-enumeration-false-positives.html'), 'utf8');
  assert.match(html, /Observed case: a successful GitLab request/);
  assert.match(html, /benchmark-observation-2026-10-02.json/);
});
test('worksheets are accessible downloads and explicitly illustrative', () => {
  for (const [slug, filename] of [['protect-researcher-notes', 'research-notes-retention.csv'], ['public-profile-evidence-logging', 'public-evidence-register.csv'], ['verify-osint-account-matches', 'account-match-decision-log.csv']]) {
    const csv = fs.readFileSync(path.join(root, 'assets/downloads', filename), 'utf8');
    assert.match(csv, /ILLUSTRATIVE/);
    const html = fs.readFileSync(path.join(root, 'guides', `${slug}.html`), 'utf8');
    assert.ok(html.includes(`href="/assets/downloads/${filename}" download`));
    assert.match(html, /<caption>/);
  }
});
test('rebuilding original articles cannot duplicate app notices', () => {
  for (const folder of ['guides', 'find', 'privacy', 'vs']) {
    for (const file of fs.readdirSync(path.join(root, folder)).filter(f => f.endsWith('.html'))) {
      const html = fs.readFileSync(path.join(root, folder, file), 'utf8');
      assert.ok([...html.matchAll(/data-content-app-context/g)].length <= 1, `${folder}/${file}`);
    }
  }
});
