/* Keep the optional llms.txt navigation aligned with published canonical pages.
 * This convention is not a search ranking or AI recommendation requirement.
 * Run after build-blog.js: node scripts/build-llms.js
 */
const fs = require('node:fs');
const path = require('node:path');
const { toUrlPath, fileForUrl, validDate, attribute } = require('./build-sitemap.js');

const ROOT = path.resolve(__dirname, '..');
const SITE = 'https://www.myrecon.xyz';
const START = '<!-- BEGIN GENERATED BLOG LINKS -->';
const END = '<!-- END GENERATED BLOG LINKS -->';
const markdownLabel = value => String(value).replace(/[\r\n]+/g, ' ').replace(/([\\\[\]])/g, '\\$1');

function normalizeInternalLinks(markdown, root = ROOT) {
  const configPath = path.join(root, 'vercel.json');
  const config = fs.existsSync(configPath) ? JSON.parse(fs.readFileSync(configPath, 'utf8')) : {};
  const redirects = new Map((config.redirects || []).filter(rule => !rule.source.includes(':') && !rule.has && !rule.missing).map(rule => [rule.source, rule.destination]));
  return markdown.replace(/\]\((https:\/\/(?:www\.)?myrecon\.xyz[^)\s]*)\)/g, (match, href) => {
    const url = new URL(href);
    const visited = new Set();
    while (redirects.has(url.pathname)) {
      if (visited.has(url.pathname)) throw new Error(`llms.txt redirect loop: ${href}`);
      visited.add(url.pathname);
      url.pathname = redirects.get(url.pathname);
    }
    const file = fileForUrl(url.pathname, root);
    if (file) {
      const canonical = toUrlPath(file, fs.readFileSync(file, 'utf8'), root);
      if (!canonical) throw new Error(`llms.txt invalid canonical: ${href}`);
      url.pathname = canonical;
    } else if (!fs.existsSync(path.resolve(root, `.${url.pathname}`))) {
      throw new Error(`llms.txt missing linked resource: ${href}`);
    }
    return `](${SITE}${url.pathname}${url.search}${url.hash})`;
  });
}

function blogLinks(root = ROOT) {
  const source = path.join(root, 'content', 'blog');
  if (!fs.existsSync(source)) return [];
  const records = [];
  for (const filename of fs.readdirSync(source).filter(name => name.endsWith('.html')).sort()) {
    const raw = fs.readFileSync(path.join(source, filename), 'utf8');
    const match = raw.match(/^\s*<!--\s*(\{[\s\S]*?\})\s*-->/);
    if (!match) throw new Error(`${filename}: missing article metadata for llms.txt`);
    const meta = JSON.parse(match[1]);
    const file = path.join(root, 'blog', filename);
    if (!fs.existsSync(file)) throw new Error(`${filename}: build the blog before llms.txt`);
    const html = fs.readFileSync(file, 'utf8');
    const excluded = [...html.matchAll(/<meta\b[^>]*>/gi)].some(([tag]) =>
      /^(?:robots|googlebot|bingbot|applebot)$/i.test(attribute(tag, 'name') || '') && /\b(?:noindex|none)\b/i.test(attribute(tag, 'content') || ''));
    if (excluded) continue;
    const route = toUrlPath(file, html, root);
    if (!route || fileForUrl(route, root) !== file) throw new Error(`${filename}: article must have its own local canonical`);
    if (!meta.headline || !meta.description) throw new Error(`${filename}: article headline and description are required`);
    records.push({ route, title: meta.headline, description: String(meta.description).replace(/\s+/g, ' ').trim(), date: validDate(meta.dateModified) });
  }
  return records.sort((a, b) => b.date.localeCompare(a.date) || a.route.localeCompare(b.route))
    .map(article => `- [${markdownLabel(article.title)}](${SITE}${article.route}): ${article.description}`);
}

function buildLlms(root = ROOT) {
  const target = path.join(root, 'llms.txt');
  const original = fs.readFileSync(target, 'utf8').replace(/\r\n/g, '\n');
  const begin = original.indexOf(START);
  const finish = original.indexOf(END);
  if (begin < 0 || finish < begin || original.indexOf(START, begin + START.length) >= 0 || original.indexOf(END, finish + END.length) >= 0) {
    throw new Error('llms.txt needs exactly one ordered generated blog-links block');
  }
  const links = blogLinks(root);
  const next = normalizeInternalLinks(original.slice(0, begin + START.length) + '\n' + links.join('\n') + '\n' + original.slice(finish), root);
  if (original !== next) fs.writeFileSync(target, next, 'utf8');
  console.log(`[llms] ${links.length} article links; public canonical navigation refreshed`);
  return next;
}

if (require.main === module) buildLlms();
module.exports = { normalizeInternalLinks, blogLinks, buildLlms };
