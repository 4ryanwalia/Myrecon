#!/usr/bin/env node
/* SEO audit: measures the search concepts this site is planned against.
 *
 * Read-only. It never edits a page; it prints findings and exits 0, so it can
 * run beside the build without blocking a deploy. Pass --json for machine
 * output and --gsc <file.csv> for the striking-distance report.
 *
 * What each section measures (definitions in docs/seo-search-concepts.md):
 *   cannibalisation  pages whose titles chase the same query family
 *   index bloat      thin, duplicate or near-duplicate indexable pages
 *   crawl budget     sitemap or internal links that spend a hop on a redirect
 *   entity salience  whether "MyRecon" is the central entity of key pages
 *   passages         long pages without anchored sections Google can lift
 *   fan-out / GEO    answer-first, question-shaped sections and dated facts
 *   reputation abuse third-party or sponsored content hosted on the domain
 *   striking dist.   queries at positions 11 to 20 (needs a Search Console CSV)
 *
 * The page set is the generated sitemap.xml, because that is already the
 * site's own decision about what is indexable (noindex and duplicate
 * canonicals are skipped by build-sitemap.js).
 *
 * Run: node scripts/seo-audit.js [--json] [--gsc path/to/Queries.csv]
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SITE = 'https://www.myrecon.xyz';
const args = process.argv.slice(2);
const asJson = args.includes('--json');
const gscIndex = args.indexOf('--gsc');
const gscFile = gscIndex >= 0 ? args[gscIndex + 1] : null;

// Head queries the site most wants to own. Each family lists the words a
// title must contain to count as targeting it. Order words do not matter.
const QUERY_FAMILIES = [
  { query: 'username search / username checker', all: ['username'], any: ['search', 'checker', 'lookup', 'finder'], exclude: ['reverse', 'instagram', 'tiktok', 'reddit', 'discord', 'github', 'telegram', 'twitch', 'snapchat', 'twitter', 'best', 'tools', 'benchmark', 'study', 'vs', 'false', 'fake'] },
  { query: 'reverse username lookup', all: ['reverse', 'username'] },
  { query: 'best username search tools', all: ['username'], any: ['best', 'tools'], exclude: ['instagram'] },
  { query: 'instagram username search', all: ['instagram'], any: ['username', 'handle'] },
  { query: 'digital footprint checker', all: ['footprint'], any: ['checker', 'check', 'scan'] },
];

const THIN_WORDS = 300;
const LONG_PAGE_WORDS = 900;
const LONG_SECTION_WORDS = 450;
const ANSWER_FIRST_WORDS = 70;

// ---------- helpers ----------

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8');
}

function decode(s) {
  return s.replace(/&amp;/g, '&').replace(/&#39;|&apos;/g, "'").replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ');
}

function stripTags(html) {
  return decode(html
    .replace(/<script\b[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
}

function words(text) {
  return text ? text.split(/\s+/).filter(Boolean).length : 0;
}

function mainHtml(html) {
  const m = html.match(/<main\b[\s\S]*?<\/main>/i) || html.match(/<article\b[\s\S]*?<\/article>/i);
  if (m) return m[0];
  return html.replace(/<header\b[\s\S]*?<\/header>/gi, ' ')
    .replace(/<nav\b[\s\S]*?<\/nav>/gi, ' ')
    .replace(/<footer\b[\s\S]*?<\/footer>/gi, ' ');
}

const STOP = new Set('a an and the of for to in on by with your you how what is are vs from at or our its it be can do does this that &'.split(' '));
function tokens(title) {
  return decode(title).toLowerCase()
    .replace(/\|\s*myrecon\s*$/i, '')
    .replace(/[^a-z0-9+ ]/g, ' ')
    .split(/\s+/)
    .filter(t => t && !STOP.has(t) && t !== 'myrecon')
    .map(t => t.replace(/(ings|ing|es|s)$/, '') || t);
}

function jaccard(a, b) {
  const A = new Set(a), B = new Set(b);
  let inter = 0;
  for (const t of A) if (B.has(t)) inter++;
  return inter / (A.size + B.size - inter || 1);
}

function urlToFile(urlPath) {
  let p = decodeURI(urlPath.split('#')[0].split('?')[0]);
  if (p.startsWith(SITE)) p = p.slice(SITE.length);
  if (!p.startsWith('/')) return null;
  const candidates = [];
  if (p.endsWith('/')) candidates.push(p + 'index.html');
  else if (p.endsWith('.html')) candidates.push(p);
  else candidates.push(p + '.html', p + '/index.html');
  for (const c of candidates) {
    const rel = c.replace(/^\//, '');
    if (fs.existsSync(path.join(ROOT, rel))) return rel;
  }
  return null;
}

// Vercel redirect sources, compiled to regexes. Host-conditional rules (apex
// to www) are skipped: internal links are path-only.
function loadRedirects() {
  const cfg = JSON.parse(read('vercel.json'));
  return (cfg.redirects || []).filter(r => !r.has).map(r => {
    const re = '^' + r.source
      .replace(/[.+?^${}()|[\]\\]/g, m => (m === '(' || m === ')' ? m : '\\' + m))
      .replace(/\/:[a-zA-Z]+\*/g, '(?:/.*)?')
      .replace(/:[a-zA-Z]+/g, '[^/]+') + '$';
    return { source: r.source, destination: r.destination, re: new RegExp(re) };
  });
}

function redirectFor(urlPath, redirects) {
  const p = urlPath.split('#')[0].split('?')[0];
  return redirects.find(r => r.re.test(p)) || null;
}

function jsonLd(html) {
  const out = [];
  for (const m of html.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
    try { out.push(JSON.parse(m[1])); } catch { /* the build's own gate catches parse errors */ }
  }
  const types = new Set();
  const walk = n => {
    if (Array.isArray(n)) return n.forEach(walk);
    if (n && typeof n === 'object') {
      const t = n['@type'];
      if (t) (Array.isArray(t) ? t : [t]).forEach(x => types.add(x));
      Object.values(n).forEach(walk);
    }
  };
  walk(out);
  return types;
}

// ---------- load pages ----------

function loadPages() {
  const xml = read('sitemap.xml');
  const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1])
    .filter(u => !/\.(png|jpe?g|webp|gif|svg|mp4|webm)$/i.test(u));
  const pages = [];
  const missing = [];
  for (const loc of new Set(locs)) {
    const file = urlToFile(loc);
    if (!file) { missing.push(loc); continue; }
    const html = read(file);
    const main = mainHtml(html);
    const text = stripTags(main);
    const title = decode((html.match(/<title>([^<]*)<\/title>/i) || [, ''])[1]).trim();
    const desc = decode((html.match(/<meta\s+name="description"\s+content="([^"]*)"/i) || [, ''])[1]).trim();
    const canonical = (html.match(/<link\s+rel="canonical"\s+href="([^"]+)"/i) || [, ''])[1];
    const h1 = stripTags((html.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/i) || [, ''])[1]);
    const firstP = stripTags((main.match(/<p\b[^>]*>([\s\S]*?)<\/p>/i) || [, ''])[1]);
    pages.push({ loc, file, html, main, text, words: words(text), title, desc, canonical, h1, firstP, types: jsonLd(html) });
  }
  return { pages, missing };
}

// ---------- checks ----------

function cannibalisation(pages) {
  const families = QUERY_FAMILIES.map(f => {
    const hits = pages.filter(p => {
      const t = tokens(p.title + ' ' + p.h1);
      const has = w => t.includes(w.replace(/(ings|ing|es|s)$/, '') || w);
      return f.all.every(has) && (!f.any || f.any.some(has)) && !(f.exclude || []).some(has);
    }).map(p => ({ url: p.loc.replace(SITE, ''), title: p.title, words: p.words }));
    return { query: f.query, pages: hits };
  });
  const pairs = [];
  for (let i = 0; i < pages.length; i++) {
    for (let j = i + 1; j < pages.length; j++) {
      const a = tokens(pages[i].title), b = tokens(pages[j].title);
      if (a.length < 2 || b.length < 2) continue;
      const s = jaccard(a, b);
      if (s >= 0.6) pairs.push({ score: +s.toFixed(2), a: pages[i].loc.replace(SITE, ''), b: pages[j].loc.replace(SITE, ''), titleA: pages[i].title, titleB: pages[j].title });
    }
  }
  pairs.sort((x, y) => y.score - x.score);
  return { families, pairs };
}

function indexBloat(pages, missing) {
  const thin = pages.filter(p => p.words < THIN_WORDS).map(p => ({ url: p.loc.replace(SITE, ''), words: p.words }));
  const dupTitles = groupBy(pages, p => p.title.toLowerCase()).filter(g => g.length > 1).map(g => g.map(p => p.loc.replace(SITE, '')));
  const dupDescs = groupBy(pages.filter(p => p.desc), p => p.desc.toLowerCase()).filter(g => g.length > 1).map(g => g.map(p => p.loc.replace(SITE, '')));
  const canonMismatch = pages.filter(p => p.canonical && p.canonical !== p.loc).map(p => ({ sitemap: p.loc, canonical: p.canonical }));
  const noDesc = pages.filter(p => !p.desc).map(p => p.loc.replace(SITE, ''));
  return { indexable: pages.length, thin, dupTitles, dupDescs, canonMismatch, noDesc, sitemapUnresolved: missing };
}

function groupBy(arr, key) {
  const m = new Map();
  for (const x of arr) { const k = key(x); if (!m.has(k)) m.set(k, []); m.get(k).push(x); }
  return [...m.values()];
}

function crawlBudget(pages, redirects) {
  const sitemapRedirects = pages.filter(p => redirectFor(p.loc.replace(SITE, ''), redirects)).map(p => p.loc);
  const canonicalRedirects = pages.filter(p => p.canonical && redirectFor(p.canonical.replace(SITE, ''), redirects)).map(p => ({ page: p.loc, canonical: p.canonical }));
  const viaRedirect = new Map();
  const broken = new Map();
  const inbound = new Map(pages.map(p => [p.file, 0]));
  const fileSet = new Set(pages.map(p => p.file));
  for (const p of pages) {
    const seen = new Set();
    for (const m of p.html.matchAll(/<a\b[^>]*\bhref="([^"#][^"]*)"/gi)) {
      let href = decode(m[1]);
      if (/^(mailto:|tel:|javascript:|data:)/i.test(href)) continue;
      if (/^https?:\/\//i.test(href)) {
        if (!href.startsWith(SITE)) continue;
        href = href.slice(SITE.length) || '/';
      } else if (!href.startsWith('/')) {
        href = path.posix.join('/' + path.posix.dirname(p.file), href);
      }
      const clean = href.split('#')[0].split('?')[0];
      if (!clean || /\.(png|jpe?g|webp|svg|gif|pdf|xml|txt|json|csv|md|mp4|webm|zip|apk|css|js|ico)$/i.test(clean)) continue;
      if (clean.startsWith('/api/')) continue;
      const r = redirectFor(clean, redirects);
      if (r) {
        const k = `${clean} -> ${r.destination}`;
        viaRedirect.set(k, (viaRedirect.get(k) || 0) + 1);
        continue;
      }
      const target = urlToFile(clean);
      if (!target) {
        broken.set(clean, (broken.get(clean) || 0) + 1);
        continue;
      }
      if (target !== p.file && fileSet.has(target) && !seen.has(target)) {
        seen.add(target);
        inbound.set(target, inbound.get(target) + 1);
      }
    }
  }
  const orphans = [...inbound].filter(([f, n]) => n === 0 && f !== 'index.html').map(([f]) => f);
  const weak = [...inbound].filter(([, n]) => n === 1).map(([f]) => f);
  return {
    sitemapRedirects,
    canonicalRedirects,
    linksViaRedirect: [...viaRedirect].sort((a, b) => b[1] - a[1]).map(([k, n]) => ({ link: k, count: n })),
    unresolvedLinks: [...broken].sort((a, b) => b[1] - a[1]).map(([k, n]) => ({ link: k, count: n })),
    orphans,
    singleInbound: weak,
    inbound: Object.fromEntries(inbound),
  };
}

function entitySalience(pages) {
  const KEY = /^(\/|\/username-checker(\.html)?|\/about(\.html)?|\/reverse-username-lookup(\.html)?|\/digital-footprint-checker(\.html)?|\/free-osint-tool(\.html)?|\/features(\.html)?|\/is-myrecon-legit(\.html)?)$/;
  const rows = pages.filter(p => KEY.test(p.loc.replace(SITE, '') || '/')).map(p => {
    const mentions = (p.text.match(/\bMyRecon\b/g) || []).length;
    return {
      url: p.loc.replace(SITE, '') || '/',
      inTitle: /myrecon/i.test(p.title),
      inH1: /myrecon/i.test(p.h1),
      inFirstParagraph: /myrecon/i.test(p.firstP),
      mentionsPer1000Words: +(mentions / Math.max(p.words, 1) * 1000).toFixed(1),
      orgOrAppSchema: ['Organization', 'SoftwareApplication', 'WebApplication', 'MobileApplication'].filter(t => p.types.has(t)),
    };
  });
  const orgSameAs = (() => {
    const home = pages.find(p => p.loc === SITE + '/');
    if (!home) return [];
    const m = home.html.match(/"sameAs"\s*:\s*\[([^\]]*)\]/);
    return m ? [...m[1].matchAll(/"([^"]+)"/g)].map(x => x[1]) : [];
  })();
  return { keyPages: rows, homepageSameAs: orgSameAs };
}

function sections(main) {
  // Split main content at H2s; each section keeps its heading and its text.
  const parts = main.split(/(?=<h2\b)/i);
  return parts.slice(1).map(s => {
    const head = s.match(/<h2\b([^>]*)>([\s\S]*?)<\/h2>/i);
    const attrs = head ? head[1] : '';
    const heading = head ? stripTags(head[2]) : '';
    const body = head ? s.slice(head.index + head[0].length) : s;
    const firstP = stripTags((body.match(/<p\b[^>]*>([\s\S]*?)<\/p>/i) || [, ''])[1]);
    const sub = (body.match(/<h3\b/gi) || []).length;
    return {
      heading,
      anchored: /\bid="/i.test(attrs) || /<section\b[^>]*\bid="[^"]*"[^>]*>\s*$/i.test(''),
      question: /\?\s*$/.test(heading) || /^(how|what|why|when|which|who|is|are|can|does|do|should)\b/i.test(heading),
      words: words(stripTags(body)),
      firstAnswerWords: words(firstP),
      sub,
    };
  });
}

function passagesAndFanout(pages) {
  const longPages = pages.filter(p => p.words >= LONG_PAGE_WORDS);
  const rows = longPages.map(p => {
    const secs = sections(p.main);
    // A heading counts as anchored if the h2 has an id or its wrapping section does.
    const anchoredIds = (p.main.match(/<h2\b[^>]*\bid="/gi) || []).length +
      (p.main.match(/<section\b[^>]*\bid="[^"]*"[^>]*>\s*(?:<[^h][^>]*>\s*)*<h2\b(?![^>]*\bid=)/gi) || []).length;
    return {
      url: p.loc.replace(SITE, '') || '/',
      words: p.words,
      h2: secs.length,
      anchored: Math.min(anchoredIds, secs.length),
      questionH2: secs.filter(s => s.question).length,
      longUnbrokenSections: secs.filter(s => s.words > LONG_SECTION_WORDS && s.sub === 0).map(s => s.heading),
      slowAnswers: secs.filter(s => s.firstAnswerWords > ANSWER_FIRST_WORDS).length,
      faq: p.types.has('FAQPage'),
      dataset: p.types.has('Dataset'),
      datedFact: /\b(?:measured|checked|tested|as of|updated)\b[^.]{0,40}\b20\d\d\b/i.test(p.text),
    };
  });
  const totals = {
    longPages: rows.length,
    noH2: rows.filter(r => r.h2 === 0).length,
    fullyAnchored: rows.filter(r => r.h2 > 0 && r.anchored === r.h2).length,
    unanchored: rows.filter(r => r.h2 > 0 && r.anchored === 0).length,
    withQuestionH2: rows.filter(r => r.questionH2 > 0).length,
    withFaqSchema: rows.filter(r => r.faq).length,
    withDataset: rows.filter(r => r.dataset).length,
    withDatedFact: rows.filter(r => r.datedFact).length,
  };
  return { totals, pages: rows };
}

function reputationAbuse(pages) {
  const flagged = [];
  for (const p of pages) {
    const reasons = [];
    if (/rel="[^"]*\bsponsored\b/i.test(p.html)) reasons.push('rel=sponsored link');
    if (/\b(guest post|sponsored post|paid partnership|advertorial|promo code|coupon code)\b/i.test(p.text)) reasons.push('sponsored/guest wording');
    const authors = [...p.html.matchAll(/"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"/g)].map(m => m[1]);
    const outside = authors.filter(a => !/myrecon/i.test(a));
    if (outside.length) reasons.push('author: ' + [...new Set(outside)].join(', '));
    if (reasons.length) flagged.push({ url: p.loc.replace(SITE, '') || '/', reasons });
  }
  return { flagged };
}

function strikingDistance(file, pages) {
  if (!file) return { available: false, note: 'Pass --gsc <Queries.csv or Pages.csv> exported from Search Console > Performance.' };
  const raw = fs.readFileSync(file, 'utf8').replace(/^﻿/, '');
  const lines = raw.split(/\r?\n/).filter(Boolean);
  const split = l => l.match(/("([^"]|"")*"|[^,]*)(,|$)/g).slice(0, -1).map(c => c.replace(/,$/, '').replace(/^"|"$/g, '').replace(/""/g, '"'));
  const head = split(lines[0]).map(h => h.toLowerCase());
  const col = names => head.findIndex(h => names.some(n => h.includes(n)));
  const key = col(['top queries', 'query', 'top pages', 'page']);
  const pos = col(['position']);
  const imp = col(['impressions']);
  const clk = col(['clicks']);
  if (key < 0 || pos < 0) return { available: false, note: `Could not find query/page and position columns in ${file}.` };
  const rows = lines.slice(1).map(split).map(c => ({
    key: c[key], position: parseFloat(c[pos]), impressions: parseInt(c[imp], 10) || 0, clicks: parseInt(c[clk], 10) || 0,
  })).filter(r => r.position >= 10.5 && r.position <= 20.5);
  rows.sort((a, b) => b.impressions - a.impressions);
  const known = new Map(pages.map(p => [p.loc, p]));
  return {
    available: true,
    rows: rows.map(r => ({ ...r, onSite: known.has(r.key) ? known.get(r.key).file : undefined })),
    note: rows.length && rows.every(r => r.impressions < 10)
      ? 'Every striking-distance row has under 10 impressions: too little evidence to rewrite a page for any one query.'
      : '',
  };
}

// ---------- report ----------

function main() {
  const { pages, missing } = loadPages();
  const redirects = loadRedirects();
  const report = {
    generated: new Date().toISOString(),
    cannibalisation: cannibalisation(pages),
    indexBloat: indexBloat(pages, missing),
    crawlBudget: crawlBudget(pages, redirects),
    entitySalience: entitySalience(pages),
    passages: passagesAndFanout(pages),
    reputationAbuse: reputationAbuse(pages),
    strikingDistance: strikingDistance(gscFile, pages),
  };
  if (asJson) {
    const out = { ...report, crawlBudget: { ...report.crawlBudget } };
    delete out.crawlBudget.inbound;
    process.stdout.write(JSON.stringify(out, null, 2) + '\n');
    return;
  }
  const L = console.log;
  const c = report.cannibalisation;
  L(`\n== Keyword cannibalisation ==`);
  for (const f of c.families) {
    L(`  "${f.query}": ${f.pages.length} page(s)${f.pages.length > 1 ? '  <- competing' : ''}`);
    for (const p of f.pages) L(`      ${p.url}  (${p.words}w)  ${p.title}`);
  }
  L(`  Near-identical title pairs (token overlap >= 0.6): ${c.pairs.length}`);
  for (const p of c.pairs.slice(0, 25)) L(`      ${p.score}  ${p.a}  <>  ${p.b}`);

  const b = report.indexBloat;
  L(`\n== Index bloat ==`);
  L(`  Indexable URLs in sitemap: ${b.indexable}`);
  L(`  Thin (< ${THIN_WORDS} words in main content): ${b.thin.length}`);
  for (const t of b.thin) L(`      ${t.url} (${t.words}w)`);
  L(`  Duplicate titles: ${b.dupTitles.length}  Duplicate descriptions: ${b.dupDescs.length}  Missing description: ${b.noDesc.length}`);
  for (const g of [...b.dupTitles, ...b.dupDescs]) L(`      ${g.join('  =  ')}`);
  L(`  Sitemap URL differs from page canonical: ${b.canonMismatch.length}`);
  for (const m of b.canonMismatch.slice(0, 20)) L(`      ${m.sitemap}  ->  ${m.canonical}`);
  if (b.sitemapUnresolved.length) L(`  Sitemap URLs with no file on disk: ${b.sitemapUnresolved.join(', ')}`);

  const k = report.crawlBudget;
  L(`\n== Crawl budget ==`);
  L(`  Sitemap URLs that redirect: ${k.sitemapRedirects.length}`);
  for (const u of k.sitemapRedirects) L(`      ${u}`);
  L(`  Canonicals that redirect: ${k.canonicalRedirects.length}`);
  for (const u of k.canonicalRedirects) L(`      ${u.page} -> ${u.canonical}`);
  L(`  Internal links spending a hop on a redirect: ${k.linksViaRedirect.reduce((s, x) => s + x.count, 0)} (${k.linksViaRedirect.length} distinct)`);
  for (const x of k.linksViaRedirect.slice(0, 20)) L(`      ${x.count}x  ${x.link}`);
  L(`  Internal links that resolve to no file or rewrite: ${k.unresolvedLinks.length} distinct`);
  for (const x of k.unresolvedLinks.slice(0, 20)) L(`      ${x.count}x  ${x.link}`);
  L(`  Orphan indexable pages (no inbound link from another sitemap page): ${k.orphans.length}`);
  for (const o of k.orphans) L(`      ${o}`);
  L(`  Pages with exactly one inbound link: ${k.singleInbound.length}`);

  const e = report.entitySalience;
  L(`\n== Entity salience (MyRecon) ==`);
  for (const r of e.keyPages) L(`  ${r.url.padEnd(34)} title:${r.inTitle ? 'y' : 'N'} h1:${r.inH1 ? 'y' : 'N'} first-para:${r.inFirstParagraph ? 'y' : 'N'} per-1000w:${r.mentionsPer1000Words} schema:${r.orgOrAppSchema.join('/') || 'NONE'}`);
  L(`  Homepage sameAs links: ${e.homepageSameAs.length ? e.homepageSameAs.join(', ') : 'NONE'}`);

  const p = report.passages;
  L(`\n== Passage ranking + query fan-out / GEO (pages >= ${LONG_PAGE_WORDS} words) ==`);
  const t = p.totals;
  L(`  Long pages: ${t.longPages}  no H2: ${t.noH2}  every H2 anchored: ${t.fullyAnchored}  no H2 anchored: ${t.unanchored}`);
  L(`  With question-shaped H2: ${t.withQuestionH2}  FAQPage schema: ${t.withFaqSchema}  Dataset schema: ${t.withDataset}  dated fact in text: ${t.withDatedFact}`);
  const worst = p.pages.filter(r => r.h2 > 0 && r.anchored === 0).sort((a, b) => b.words - a.words).slice(0, 15);
  if (worst.length) L(`  Largest pages with no anchored H2:`);
  for (const r of worst) L(`      ${r.url} (${r.words}w, ${r.h2} H2)`);

  L(`\n== Site reputation abuse ==`);
  const r = report.reputationAbuse;
  L(`  Pages with third-party/sponsored signals: ${r.flagged.length}`);
  for (const f of r.flagged) L(`      ${f.url}: ${f.reasons.join('; ')}`);

  L(`\n== Striking distance (positions 11-20) ==`);
  const s = report.strikingDistance;
  if (!s.available) L(`  ${s.note}`);
  else {
    L(`  ${s.rows.length} row(s)`);
    for (const x of s.rows.slice(0, 40)) L(`      pos ${x.position.toFixed(1).padStart(5)}  ${String(x.impressions).padStart(5)} impr  ${x.key}`);
    if (s.note) L(`  ${s.note}`);
  }
  L('');
}

main();
