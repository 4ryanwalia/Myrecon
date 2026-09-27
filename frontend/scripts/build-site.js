const { spawnSync } = require('node:child_process');

const scripts = [
  'gen-env.js',
  'build-breaches.js',
  'build-case-files.js',
  'build-data-api.js',
  'build-seo-pages.js',
  'build-blog.js',
  'enhance-content-pages.js',
  'enhance-site-footer.js',
  'version-site-assets.js',
  'build-sitemap.js',
];

for (const script of scripts) {
  const result = spawnSync(process.execPath, [`scripts/${script}`], {
    stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
