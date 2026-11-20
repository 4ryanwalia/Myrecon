const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const root = path.resolve(__dirname, '..');
// Comments are dropped so the copy rules can quote what the page must never say.
const nudge = fs.readFileSync(path.join(root, 'assets/js/app-nudge.js'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

test('build installs the nudge after the homepage restore', () => {
  const build = fs.readFileSync(path.join(root, 'scripts/build-site.js'), 'utf8');
  assert.ok(build.indexOf("require('./install-app-nudge').run()") > build.indexOf('fs.writeFileSync(homepagePath, homepageContents)'));
});

test('installer is idempotent, versioned, and skips app, checkout, embed and AdSense-review pages', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'myrecon-nudge-'));
  try {
    fs.mkdirSync(path.join(tmp, 'scripts'));
    fs.mkdirSync(path.join(tmp, 'assets/js'), {recursive: true});
    fs.copyFileSync(path.join(root, 'scripts/install-app-nudge.js'), path.join(tmp, 'scripts/install-app-nudge.js'));
    fs.copyFileSync(path.join(root, 'assets/js/app-nudge.js'), path.join(tmp, 'assets/js/app-nudge.js'));
    const page = '<html><head></head><body><p>Original</p></body></html>';
    for (const rel of ['index.html', 'username-checker.html', 'breaches/x.html', 'guides/a.html', 'blog/b.html', 'breaches/case-files/c.html', 'app.html', 'pricing.html', 'badge.html', 'worker-console/index.html']) {
      fs.mkdirSync(path.dirname(path.join(tmp, rel)), {recursive: true});
      fs.writeFileSync(path.join(tmp, rel), page);
    }
    fs.writeFileSync(path.join(tmp, 'pricing.html'), page.replace('</body>', '<script src="/assets/js/app-nudge.js?v=old" defer></script>\n</body>'));
    const run = () => execFileSync(process.execPath, [path.join(tmp, 'scripts/install-app-nudge.js')]).toString();
    run();
    const second = run();
    assert.match(second, /0 page\(s\) updated, 0 removed/);
    for (const rel of ['index.html', 'username-checker.html', 'breaches/x.html']) {
      const html = fs.readFileSync(path.join(tmp, rel), 'utf8');
      assert.equal((html.match(/app-nudge\.js\?v=[0-9a-f]{10}"/g) || []).length, 1, rel);
      assert.ok(html.indexOf('app-nudge.js') < html.indexOf('</body>'), rel);
    }
    // guides, blog and case files stay popup-free during the AdSense review.
    for (const rel of ['app.html', 'pricing.html', 'badge.html', 'worker-console/index.html', 'guides/a.html', 'blog/b.html', 'breaches/case-files/c.html']) {
      assert.doesNotMatch(fs.readFileSync(path.join(tmp, rel), 'utf8'), /app-nudge/, rel);
    }
  } finally {
    fs.rmSync(tmp, {recursive: true, force: true});
  }
});

test('nudge copy stays honest and points at the real listing', () => {
  // The app shows ads, so blanket privacy claims would be false.
  assert.doesNotMatch(nudge, /nothing is shared|never shared|no data|not shared with anyone|100% private/i);
  // Only the username scan is on-device; enrichment and fallbacks reach the backend.
  assert.doesNotMatch(nudge, /lookups run (from|on) your|all (lookups|searches|checks) run|everything runs/i);
  // Never imply the website leaks data.
  assert.doesNotMatch(nudge, /unlike (the|our) website|safer than|website (leaks|shares)/i);
  assert.doesNotMatch(nudge, new RegExp(String.fromCharCode(0x2014)));
  assert.match(nudge, /id=com\.Myrecon\.osint/);
  assert.match(nudge, /utm_campaign=web_nudge_/);
  assert.doesNotMatch(nudge, /[?&](ref|referrer)=[0-9a-f-]{8}/i, 'must not look like a referral invite');
  // iPhones get nothing, Android WebViews (the app itself) get nothing.
  assert.match(nudge, /if \(otherMobile\) return;/);
  assert.match(nudge, /; wv\\\)/);
});
