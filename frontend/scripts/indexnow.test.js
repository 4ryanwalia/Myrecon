const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { publicUrl, renderedChangedUrls } = require('./indexnow');

test('uses clean canonical URLs and directory roots', () => {
  assert.equal(publicUrl('frontend/find/github-profile.html', '<title>GitHub</title><link href="https://www.myrecon.xyz/find/github-profile" rel="canonical">'), 'https://www.myrecon.xyz/find/github-profile');
  assert.equal(publicUrl('frontend/guides/index.html', '<title>Guides</title>'), 'https://www.myrecon.xyz/guides/');
  assert.equal(publicUrl('frontend/index.html', '<title>Home</title>'), 'https://www.myrecon.xyz/');
});

test('does not submit private, excluded, or external pages', () => {
  for (const file of ['frontend/404.html', 'frontend/content/article.html', 'frontend/tests/example.html']) {
    assert.equal(publicUrl(file, '<title>Page</title>'), null);
  }
  assert.equal(publicUrl('frontend/account.html', '<title>Account</title><meta content="noindex, follow" name="robots">'), null);
  assert.equal(publicUrl('frontend/other.html', '<title>Other</title><link rel="canonical" href="https://example.com/">'), null);
  assert.equal(publicUrl('frontend/fragment.html', '<p>Fragment</p>'), null);
});

test('submits only pages whose rendered public HTML changed', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'myrecon-indexnow-'));
  const before = path.join(root, 'before');
  const after = path.join(root, 'after');
  try {
    fs.mkdirSync(path.join(before, 'guides'), { recursive: true });
    fs.mkdirSync(path.join(after, 'guides'), { recursive: true });
    fs.mkdirSync(path.join(after, 'content'), { recursive: true });
    const unchanged = '<title>Guide</title><link rel="canonical" href="https://www.myrecon.xyz/guides/">';
    fs.writeFileSync(path.join(before, 'guides', 'index.html'), unchanged);
    fs.writeFileSync(path.join(after, 'guides', 'index.html'), unchanged);
    fs.writeFileSync(path.join(before, 'guides', 'privacy.html'), '<title>Privacy</title><link rel="canonical" href="https://www.myrecon.xyz/guides/privacy">old');
    fs.writeFileSync(path.join(after, 'guides', 'privacy.html'), '<title>Privacy</title><link rel="canonical" href="https://www.myrecon.xyz/guides/privacy">new');
    fs.writeFileSync(path.join(after, 'guides', 'new.html'), '<title>New</title><link rel="canonical" href="https://www.myrecon.xyz/guides/new">');
    fs.writeFileSync(path.join(after, 'content', 'fragment.html'), '<title>Fragment</title>');
    assert.deepEqual(renderedChangedUrls(before, after), [
      'https://www.myrecon.xyz/guides/new',
      'https://www.myrecon.xyz/guides/privacy',
    ]);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
