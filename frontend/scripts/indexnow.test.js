const { test } = require('node:test');
const assert = require('node:assert/strict');
const { publicUrl } = require('./indexnow');

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
