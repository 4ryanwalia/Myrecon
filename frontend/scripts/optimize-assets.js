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
  const selfHostedFonts = fs.existsSync(path.join(root, 'assets/css/fonts.css'));
  for (const file of pages) {
    const before = fs.readFileSync(file, 'utf8');
    const responsive = sizeStoryPhotos(before);
    const after = bundleStyles(root, selfHostFonts(responsive, selfHostedFonts).replace(pattern, (all, attr, quote, url, kind, name, extension) => {
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
    }));
    if (before !== after) {
      for (let attempt = 0; attempt < 5; attempt++) {
        try {
          fs.writeFileSync(file, after);
          break;
        } catch (err) {
          if (attempt === 4) throw err;
          Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 150 * (attempt + 1));
        }
      }
    }
  }
  const report = { pages: pages.length, assets: Object.fromEntries(assets) };
  fs.writeFileSync(path.join(root, '.asset-optimization.json'), JSON.stringify(report, null, 2) + '\n');
  const values = [...assets.values()];
  console.log(`[optimize] ${assets.size} shared assets: ${values.reduce((s, a) => s + a.before, 0)} -> ${values.reduce((s, a) => s + a.after, 0)} bytes; ${pages.length} pages`);
  return report;
}
// Lazy article photos can use the browser's actual layout width.
function sizeStoryPhotos(html) {
  return html.replace(/(<figure class="story-photo">)(<img\b[^>]+>)/g, (figure, opening, img) => {
    const src = img.match(/\bsrc="(https:\/\/images\.unsplash\.com\/photo-[^"]+)"/);
    if (!src || /\bsrcset=/.test(img)) return figure;
    const url = new URL(src[1].replaceAll('&amp;', '&'));
    const candidates = [400, 720, 960, 1200].map(width => {
      url.searchParams.set('w', width);
      return `${url.href.replaceAll('&', '&amp;')} ${width}w`;
    });
    const sizes = '(max-width: 900px) calc(100vw - 40px), 860px';
    const auto = img.includes('loading="lazy"') ? 'auto, ' : '';
    return opening + img.replace(/>$/, ` srcset="${candidates.join(', ')}" sizes="${auto}${sizes}">`);
  });
}
// Google Fonts costs two extra connections before first paint. The same Inter and
// JetBrains Mono files are served from this origin by assets/css/fonts.css.
const GOOGLE_FONTS = /<link\b[^>]*\bhref="https:\/\/fonts\.googleapis\.com\/css2\?family=(?:Inter|JetBrains\+Mono)[^"]*"[^>]*>/gi;
const FONT_PRECONNECT = /[ \t]*<link\b[^>]*\brel="preconnect"[^>]*\bhref="https:\/\/fonts\.(?:googleapis|gstatic)\.com"[^>]*>\r?\n?/gi;
// The Latin Inter file nearly every page renders its text with.
const INTER_LATIN = '/assets/fonts/inter-UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2';
function selfHostFonts(html, available) {
  if (!available) return html;
  const links = [...html.matchAll(GOOGLE_FONTS)].map(([tag]) => tag);
  // Only the families fonts.css provides; a page asking for any other keeps Google.
  const families = links.flatMap(tag => [...tag.matchAll(/family=([^:&"]+)/g)].map(match => match[1]));
  if (!links.length || families.some(name => name !== 'Inter' && name !== 'JetBrains+Mono')) return html;
  let first = true;
  return html.replace(FONT_PRECONNECT, '').replace(GOOGLE_FONTS, () => {
    if (!first) return '';
    first = false;
    return `<link rel="preload" href="${INTER_LATIN}" as="font" type="font/woff2" crossorigin>\n  <link rel="stylesheet" href="/assets/css/fonts.css">`;
  });
}

// Every stylesheet in <head> blocks first paint, and each one is a separate request.
// Join each run of optimized stylesheets into one file, in the same order. A run
// ends at anything that could change the cascade between them: an inline <style>
// or a stylesheet that is not ours (or has media/onload attributes).
const PLAIN_SHEET = /^<link rel="stylesheet" href="(\/assets\/optimized\/css\/[\w.-]+\.css)"\s*\/?>$/;
function bundleStyles(root, html) {
  const head = /<head\b[^>]*>([\s\S]*?)<\/head>/i.exec(html);
  if (!head) return html;
  const tags = [...head[1].matchAll(/<style\b[\s\S]*?<\/style>|<link\b[^>]*>/gi)];
  const runs = [];
  let run = [];
  for (const match of tags) {
    const sheet = PLAIN_SHEET.exec(match[0]);
    if (sheet) { run.push({ tag: match[0], href: sheet[1] }); continue; }
    if (/^<style/i.test(match[0]) || /\brel=["']?stylesheet/i.test(match[0])) { runs.push(run); run = []; }
  }
  runs.push(run);
  let out = head[1];
  for (const group of runs.filter(group => group.length > 1)) {
    const css = group.map(item => fs.readFileSync(path.join(root, item.href), 'utf8')).join('\n');
    const hash = crypto.createHash('sha256').update(css).digest('hex').slice(0, 12);
    const href = `/assets/optimized/css/bundle.${hash}.css`;
    const destination = path.join(root, href);
    if (!fs.existsSync(destination)) fs.writeFileSync(destination, css);
    out = out.replace(group[0].tag, `<link rel="stylesheet" href="${href}">`);
    for (const item of group.slice(1)) out = out.replace(new RegExp(`[ \\t]*${item.tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\r?\\n?`), '');
  }
  return html.slice(0, head.index) + head[0].replace(head[1], () => out) + html.slice(head.index + head[0].length);
}

if (require.main === module) optimizeAssets();
module.exports = { optimizeAssets, bundleStyles, selfHostFonts };
