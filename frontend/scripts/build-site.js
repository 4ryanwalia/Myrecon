const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '..');
const SKIP_DIRS = new Set(['.git', '.vercel', 'content', 'data', 'node_modules', 'scripts']);

/**
 * Capture public HTML before and after the build. The sitemap uses this to
 * publish an honest lastmod when a generator changes a rendered page without
 * changing that generated HTML file in Git.
 */
function publicHtmlHashes(dir = ROOT, hashes = new Map()) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.') || SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) publicHtmlHashes(full, hashes);
    else if (entry.name.endsWith('.html')) {
      const rel = path.relative(ROOT, full).split(path.sep).join('/');
      hashes.set(rel, crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex'));
    }
  }
  return hashes;
}

function changedHtmlPaths(before, after) {
  return [...new Set([...before.keys(), ...after.keys()])]
    .filter(file => before.get(file) !== after.get(file))
    .sort();
}

function latestFrontendCommitDate() {
  try {
    const timestamp = execFileSync('git', ['log', '-1', '--format=%ct', '--', 'frontend'], {
      cwd: path.resolve(ROOT, '..'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    if (!/^\d+$/.test(timestamp)) return '';
    const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' })
      .formatToParts(new Date(Number(timestamp) * 1000));
    return ['year', 'month', 'day'].map(type => parts.find(part => part.type === type).value).join('-');
  } catch {
    return '';
  }
}

const scripts = [
  'gen-env.js',
  'build-breaches.js',
  'build-case-files.js',
  'build-data-api.js',
  'build-seo-pages.js',
  'build-blog.js',
  'build-llms.js',
  'enhance-content-pages.js',
  'enhance-site-footer.js',
  'build-discovery-pages.js',
  'finalize-editorial.js',
  'version-site-assets.js',
  'install-google-tag.js',
];

const before = publicHtmlHashes();
for (const script of scripts) {
  const result = spawnSync(process.execPath, [`scripts/${script}`], {
    cwd: ROOT,
    stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

const changed = changedHtmlPaths(before, publicHtmlHashes());
const date = changed.length ? latestFrontendCommitDate() : '';
const sitemapEnvironment = { ...process.env };
if (changed.length && date) {
  sitemapEnvironment.MYRECON_SITEMAP_CHANGED_FILES = JSON.stringify(changed);
  sitemapEnvironment.MYRECON_SITEMAP_CHANGED_DATE = date;
  console.log(`[site] ${changed.length} rendered page change(s); sitemap lastmod set to ${date}`);
}

const sitemapResult = spawnSync(process.execPath, ['scripts/build-sitemap.js'], {
  cwd: ROOT,
  env: sitemapEnvironment,
  stdio: 'inherit',
});
if (sitemapResult.error) throw sitemapResult.error;
if (sitemapResult.status !== 0) process.exit(sitemapResult.status ?? 1);
