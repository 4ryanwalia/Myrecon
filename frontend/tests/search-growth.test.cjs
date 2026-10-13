const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const media = require('../content/blog-media.json');
const schemas = html => [...html.matchAll(/<script\b[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)].flatMap(([,s]) => {const v=JSON.parse(s);return v['@graph'] || [v];});
test('watch pages expose playable assets, captions, source links and matching video metadata', () => {
 const sitemap = fs.readFileSync(path.join(root,'sitemap.xml'),'utf8');
 for (const [slug,m] of Object.entries(media)) {
  const route = `/videos/${slug}.html`;
  const html = fs.readFileSync(path.join(root, route),'utf8');
  assert.equal((html.match(/<h1\b/g)||[]).length,1);
  assert.equal((html.match(/<video\b/g)||[]).length,1);
  const video=schemas(html).find(v=>v['@type']==='VideoObject');
  assert.equal(video.name,m.title);
  assert.ok(html.includes(`src="${new URL(video.contentUrl).pathname}"`));
  assert.ok(html.includes(`poster="${new URL(video.thumbnailUrl).pathname}"`));
  assert.ok(html.includes(`src="/assets/media/blog/${slug}.vtt"`));
  assert.ok(html.includes(`href="/blog/${slug}.html"`));
  assert.ok(sitemap.includes('https://www.myrecon.xyz'+route));
  assert.ok(html.includes('aria-current="page"'));
  for(const url of [video.contentUrl,video.thumbnailUrl]) assert.ok(fs.existsSync(path.join(root,new URL(url).pathname)));
 }
});
test('cleanup and email guides have query-led visible content and direct discovery links',()=>{
 const guide=fs.readFileSync(path.join(root,'guides/reduce-your-digital-footprint.html'),'utf8');
 assert.ok(guide.includes('Source removal and search removal are different'));
 assert.ok(guide.includes('aria-label="Breadcrumb"'));
 const home=fs.readFileSync(path.join(root,'index.html'),'utf8');
 assert.ok(home.includes('href="/videos/"'));
 assert.ok(home.includes('digital footprint checker for email and usernames'));
});
