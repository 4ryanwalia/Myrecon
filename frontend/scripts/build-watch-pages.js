const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const site = 'https://www.myrecon.xyz';
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
const json = value => JSON.stringify(value).replace(/</g, '\\u003c');
const media = JSON.parse(fs.readFileSync(path.join(root, 'content/blog-media.json'), 'utf8'));
const out = path.join(root, 'videos');
fs.mkdirSync(out, { recursive: true });
const template = fs.readFileSync(path.join(root, 'about.html'), 'utf8');
function page(title, description, route, body, extra = []) {
  const url = site + route;
  const crumbs = [{ '@type': 'ListItem', position: 1, name: 'MyRecon', item: site + '/' }, { '@type': 'ListItem', position: 2, name: 'Videos', item: site + '/videos/' }];
  if (route !== '/videos/') crumbs.push({ '@type': 'ListItem', position: 3, name: title, item: url });
  let html = template.replace(/<script\b[^>]*type="application\/ld\+json"[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<title>[\s\S]*?<\/title>/, `<title>${esc(title)} | MyRecon</title>`)
    .replace(/(<meta\b[^>]*(?:name="(?:description|twitter:description)"|property="og:description")[^>]*content=")[^"]*/g, (_, before) => before + esc(description))
    .replace(/(<meta\b[^>]*(?:name="twitter:title"|property="og:title")[^>]*content=")[^"]*/g, (_, before) => before + esc(title))
    .replace(/https:\/\/www\.myrecon\.xyz\/about\.html/g, url)
    .replace(/<main\b[^>]*>[\s\S]*?<\/main>/, `<main id="main" class="container"><article class="article"><h1>${esc(title)}</h1>${body}</article></main>`);
  const schema = { '@context': 'https://schema.org', '@graph': [{ '@type': 'BreadcrumbList', itemListElement: crumbs }, ...extra] };
  return html.replace(/[ \t]+$/gm, '').replace('</head>', `<link rel="stylesheet" href="/assets/css/search-discovery.css"><script type="application/ld+json">${json(schema)}</script></head>`);
}
for (const [slug, m] of Object.entries(media)) {
  for (const suffix of ['.mp4', '-poster.jpg', '.vtt']) if (!fs.existsSync(path.join(root, 'assets/media/blog', slug + suffix))) throw Error('Missing video asset: ' + slug + suffix);
  const route = `/videos/${slug}.html`;
  const video = { '@type': 'VideoObject', '@id': site + route + '#video', name: m.title, description: m.description, uploadDate: m.uploadDate, thumbnailUrl: site + `/assets/media/blog/${slug}-poster.jpg`, contentUrl: site + `/assets/media/blog/${slug}.mp4`, duration: 'PT32S', inLanguage: 'en', transcript: m.steps.map(([h,t]) => `${h}. ${t}`).join(' '), mainEntityOfPage: site + route };
  const body = `<video class="watch-video" controls playsinline preload="metadata" width="1280" height="720" poster="/assets/media/blog/${slug}-poster.jpg" aria-label="${esc(m.title)}"><source src="/assets/media/blog/${slug}.mp4" type="video/mp4"><track kind="captions" src="/assets/media/blog/${slug}.vtt" srclang="en" label="English" default></video><p>${esc(m.description)}</p><p>32 seconds. Silent explainer with on-screen text and English captions.</p><h2>Video transcript</h2><ol>${m.steps.map(([h,t]) => `<li><strong>${esc(h)}.</strong> ${esc(t)}</li>`).join('')}</ol><h2>Put the workflow into practice</h2><p><a href="/blog/${slug}.html">Read the full guide, sources and limitations</a>, or <a href="/videos/">browse all explainers</a>.</p>`;
  fs.writeFileSync(path.join(out, slug + '.html'), page(m.title, m.description, route, body, [video]));
  const articlePath = path.join(root, 'blog', slug + '.html');
  let article = fs.readFileSync(articlePath, 'utf8');
  if (!article.includes(`href="${route}"`)) article = article.replace('</video>', `</video><p><a href="${route}">Watch this explainer on its dedicated video page</a>.</p>`);
  fs.writeFileSync(articlePath, article);
}
fs.writeFileSync(path.join(out, 'index.html'), page('Public-source research video guides', 'Short captioned explainers for username checks, public-source research and digital footprint cleanup.', '/videos/', `<p>Choose a short workflow, watch the captioned explainer, then follow the full sourced guide.</p><ul>${Object.entries(media).map(([slug,m]) => `<li><a href="/videos/${slug}.html">${esc(m.title)}</a><p>${esc(m.description)}</p></li>`).join('')}</ul>`));
console.log(`[videos] Built ${Object.keys(media).length} watch pages and video hub`);
