#!/usr/bin/env node
/* Give every H2 in a page's main content a stable id.
 *
 * Why: Google ranks individual passages of long pages and can send a searcher
 * straight to one with a "jump to" link or a #:~:text= fragment, and AI
 * answers cite a section URL when there is one to cite. A section without an
 * id cannot be linked to, shared or cited on its own. 36 of the site's long
 * guides had no anchored H2 at all (scripts/seo-audit.js, 15 Nov 2026).
 *
 * Rules:
 * - Only H2s inside <main> or <article>; header, footer and nav are left alone.
 * - An H2 that already has an id keeps it. Ids are slugs of the heading text,
 *   made unique against every id already in the page, so reruns are no-ops.
 * - index.html is skipped: build-site.js restores the hand-authored homepage.
 *
 * Run: node scripts/anchor-headings.js
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SKIP_DIRS = new Set(['.git', '.vercel', 'content', 'data', 'node_modules', 'scripts', 'tests', 'worker-console', 'assets']);

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.') || SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.name.endsWith('.html')) out.push(full);
  }
  return out;
}

function slug(text) {
  return text
    .replace(/<[^>]+>/g, ' ')
    .replace(/&[a-z#0-9]+;/gi, ' ')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .split('-').slice(0, 8).join('-') || 'section';
}

function anchor(html) {
  const used = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map(m => m[1]));
  let changed = 0;
  const fix = block => block.replace(/<h2\b([^>]*)>([\s\S]*?)<\/h2>/gi, (whole, attrs, inner) => {
    if (/\sid=/.test(attrs)) return whole;
    const base = slug(inner);
    let id = base;
    for (let n = 2; used.has(id); n++) id = `${base}-${n}`;
    used.add(id);
    changed++;
    return `<h2${attrs} id="${id}">${inner}</h2>`;
  });
  let out = html.replace(/<main\b[\s\S]*?<\/main>/i, fix);
  if (!changed && !/<main\b/i.test(html)) out = html.replace(/<article\b[\s\S]*?<\/article>/gi, fix);
  return { out, changed };
}

function run() {
let files = 0;
let headings = 0;
for (const file of walk(ROOT)) {
  const rel = path.relative(ROOT, file).split(path.sep).join('/');
  if (rel === 'index.html') continue;
  const html = fs.readFileSync(file, 'utf8');
  const { out, changed } = anchor(html);
  if (changed) {
    fs.writeFileSync(file, out);
    files++;
    headings += changed;
  }
}
console.log(`[anchor-headings] ${headings} H2 id(s) added across ${files} page(s)`);
}

if (require.main === module) run();
module.exports = { anchor, slug, run };
