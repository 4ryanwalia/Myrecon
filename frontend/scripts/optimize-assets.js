/* Deployment-only optimization. Keep authored assets readable and unchanged. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { transformSync } = require('esbuild');
const ROOT = path.resolve(__dirname, '..');

function optimizeAssets(root = ROOT) {
  const assets = new Map();
  const pages = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith('.') || ['assets', 'content', 'data', 'scripts', 'tests', 'node_modules', 'worker-console'].includes(entry.name)) continue;
      const file = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(file);
      else if (entry.name.endsWith('.html')) pages.push(file);
    }
  }
  walk(root);
  const pattern = /\b(src|href)=(['"])(\/assets\/(?:optimized\/)?(css|js)\/([\w-]+)(?:\.[a-f0-9]{12})?\.(css|js))(?:\?[^'"]*)?\2/g;
  for (const file of pages) {
    const before = fs.readFileSync(file, 'utf8');
    const after = before.replace(pattern, (all, attr, quote, url, kind, name, extension) => {
      if (kind !== extension || name === 'env') return all;
      const source = `/assets/${kind}/${name}.${extension}`;
      if (!assets.has(source)) {
        const original = fs.readFileSync(path.join(root, source), 'utf8');
        // Moving these files must never change relative resource resolution.
        const relativeCss = [...original.matchAll(/url\(\s*['"]?([^'"\s)]+)/gi)].some(([, value]) => !/^(?:\/|data:|https?:|#)/i.test(value));
        if (extension === 'css' && (relativeCss || /@import\s/i.test(original))) return all;
        if (extension === 'js' && /(?:import\s*\(|import\s.*from\s*)['"]\./.test(original)) return all;
        const { code } = transformSync(original, { loader: extension, minify: true, target: 'es2020', legalComments: 'inline', charset: 'utf8' });
        const hash = crypto.createHash('sha256').update(code).digest('hex').slice(0, 12);
        const output = `/assets/optimized/${kind}/${name}.${hash}.${extension}`;
        const destination = path.join(root, output);
        fs.mkdirSync(path.dirname(destination), { recursive: true });
        fs.writeFileSync(destination, code);
        assets.set(source, { output, before: Buffer.byteLength(original), after: Buffer.byteLength(code) });
      }
      return `${attr}=${quote}${assets.get(source).output}${quote}`;
    });
    if (before !== after) fs.writeFileSync(file, after);
  }
  const report = { pages: pages.length, assets: Object.fromEntries(assets) };
  fs.writeFileSync(path.join(root, '.asset-optimization.json'), JSON.stringify(report, null, 2) + '\n');
  const values = [...assets.values()];
  console.log(`[optimize] ${assets.size} shared assets: ${values.reduce((s, a) => s + a.before, 0)} -> ${values.reduce((s, a) => s + a.after, 0)} bytes; ${pages.length} pages`);
  return report;
}
if (require.main === module) optimizeAssets();
module.exports = { optimizeAssets };
