export const platforms = ['GitHub', 'DEV', 'Hacker News'];
export const validHandle = value => /^[a-z0-9][a-z0-9._-]{0,38}$/i.test(value);

export function webUrl(raw) {
  try {
    const u = new URL(raw);
    return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password ? u.href : '';
  } catch { return ''; }
}

function plain(raw) {
  return String(raw || '').replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"').replace(/&#x27;|&#39;|&apos;/g, "'")
    .replace(/\s+/g, ' ').trim().slice(0, 450);
}

function link(label, raw) {
  const url = webUrl(raw);
  return url ? [{label, url}] : [];
}

// Keep a source-reported creation date distinct from a present-day profile bio.
function finding(platform, handle, url, title, date, clue, links = [], profile = false) {
  // DEV supplies a calendar date with no timezone. Midnight in the viewer's
  // timezone could shift its UTC day, so parse that format explicitly in UTC.
  const calendar = typeof date === 'string' && /^[a-z]{3,9} \d{1,2}, \d{4}$/i.test(date);
  const when = date && new Date(calendar ? date + ' 00:00:00 GMT' : date);
  return {platform, handle, url: webUrl(url), title: plain(title), clue: plain(clue),
    date: when && Number.isFinite(when.getTime()) ? when.toISOString().slice(0, 10) : '',
    profile, links};
}

async function json(url, missingOK = false) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(url, {signal: controller.signal, credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer'});
    if (missingOK && res.status === 404) return null;
    if (!res.ok) throw new Error('Source unavailable');
    return await res.json();
  } finally { clearTimeout(timer); }
}

const hnApi = 'https://hacker-news.firebaseio.com/v0';
const same = (a, b) => typeof a === 'string' && a.toLowerCase() === b.toLowerCase();

export async function checkProfile(platform, handle) {
  if (!validHandle(handle) || !platforms.includes(platform)) return {status: 'inconclusive'};
  try {
    let p, row;
    if (platform === 'GitHub') {
      p = await json('https://api.github.com/users/' + handle, true);
      if (p && same(p.login, handle)) {
        const blog = p.blog && !/^[a-z]+:/i.test(p.blog) ? 'https://' + p.blog : p.blog;
        row = finding(platform, p.login, 'https://github.com/' + p.login, 'Profile created', p.created_at,
          p.bio || p.name, link('website field', blog), true);
      }
    } else if (platform === 'DEV') {
      p = await json('https://dev.to/api/users/by_username?url=' + handle, true);
      if (p && same(p.username, handle)) {
        const links = link('website field', p.website_url);
        if (validHandle(p.github_username || '')) links.push(...link('GitHub field', 'https://github.com/' + p.github_username));
        row = finding(platform, p.username, 'https://dev.to/' + p.username, 'Profile joined DEV', p.joined_at,
          p.summary || p.name, links, true);
      }
    } else {
      p = await json(hnApi + '/user/' + handle + '.json');
      if (p && p.id === handle) {
        const links = [...String(p.about || '').matchAll(/<a\b[^>]*\bhref="([^"]+)"/gi)]
          .flatMap(m => link('about section', m[1].replace(/&amp;/g, '&'))).slice(0, 12);
        row = finding(platform, p.id, 'https://news.ycombinator.com/user?id=' + p.id, 'Profile created',
          typeof p.created === 'number' ? p.created * 1000 : '', p.about, links, true);
      }
    }
    if (p === null) return {status: 'no public profile'};
    return row ? {status: 'found', row} : {status: 'inconclusive'};
  } catch { return {status: 'inconclusive'}; }
}

async function publications(platform, handle, year) {
  if (platform === 'GitHub') {
    const rows = year
      ? (await json('https://api.github.com/search/repositories?' + new URLSearchParams({
        q: 'user:' + handle + ' fork:true created:' + year + '-01-01..' + year + '-12-31', per_page: 30,
      }))).items
      : await json('https://api.github.com/users/' + handle + '/repos?type=owner&sort=created&direction=asc&per_page=30');
    return rows.filter(r => same(r.owner?.login, handle) && webUrl(r.html_url))
      .map(r => finding(platform, handle, r.html_url, r.name, r.created_at, r.description || r.name));
  }
  if (platform === 'DEV') {
    const rows = await json('https://dev.to/api/articles?username=' + handle + '&per_page=30');
    return rows.filter(r => same(r.user?.username, handle) && webUrl(r.url))
      .map(r => finding(platform, handle, r.url, r.title, r.published_at, r.title));
  }
  const params = new URLSearchParams({tags: 'story,author_' + handle, hitsPerPage: 30});
  if (year) params.set('numericFilters', 'created_at_i>=' + Date.UTC(+year, 0, 1) / 1000 +
    ',created_at_i<' + Date.UTC(+year + 1, 0, 1) / 1000);
  const res = await json('https://hn.algolia.com/api/v1/search_by_date?' + params);
  return res.hits.filter(r => r.author === handle && /^\d+$/.test(r.objectID))
    .map(r => finding(platform, handle, 'https://news.ycombinator.com/item?id=' + r.objectID,
      r.title, r.created_at, r.title));
}

export async function discover(handle, year = '', selected = platforms) {
  const reports = await Promise.all(selected.map(async platform => {
    const {status, row} = await checkProfile(platform, handle);
    if (!row) return {platform, status, rows: []};
    try {
      return {platform, status, rows: [row, ...await publications(platform, row.handle, year)]};
    } catch { return {platform, status: 'profile found · publications inconclusive', rows: [row]}; }
  }));
  const rows = reports.flatMap(r => r.rows).filter(r => r.url && (!year || r.date.startsWith(year)))
    .sort((a, b) => (a.date || '9999').localeCompare(b.date || '9999') || a.title.localeCompare(b.title));
  return {rows, reports};
}

// Each suggestion is checked independently. A spelling resemblance alone is never a public use.
export function nearby(handle) {
  const candidates = [handle.replace(/[._-]/g, ''), handle.replace(/0/g, 'o').replace(/1/g, 'l'),
    handle.replace(/o/i, '0'), handle.replace(/l/i, '1'), handle + 's', handle + '_'];
  return [...new Set(candidates)].filter(v => v !== handle && validHandle(v)).slice(0, 2);
}

export async function compareHandles(handles, selected) {
  const memo = new Map();
  const results = [];
  for (const handle of handles) {
    for (const spelling of [handle, ...nearby(handle)]) {
      const checks = await Promise.all(selected.map(async platform => {
        const key = platform + '/' + spelling;
        if (!memo.has(key)) memo.set(key, checkProfile(platform, spelling));
        return {platform, spelling, ...await memo.get(key)};
      }));
      results.push(...checks.map(check => ({handle, ...check})));
    }
  }
  return results;
}

function nodeKey(raw) {
  const u = new URL(raw);
  u.hash = '';
  if (['github.com', 'dev.to'].includes(u.hostname)) u.pathname = u.pathname.toLowerCase();
  return u.href.replace(/\/$/, '');
}

export function graph(profiles) {
  const nodes = new Map();
  const edges = [];
  for (const p of profiles) {
    const from = nodeKey(p.url);
    nodes.set(from, p.platform + ' @' + p.handle);
    for (const l of p.links) {
      if (!webUrl(l.url)) continue;
      const to = nodeKey(l.url);
      if (from === to || edges.some(e => e.from === from && e.to === to && e.label === l.label)) continue;
      if (!nodes.has(to)) nodes.set(to, to.replace(/^https?:\/\//, ''));
      edges.push({from, to, label: l.label, source: p.url, target: l.url});
    }
  }
  return {nodes, edges, accounts: profiles.map(p => nodeKey(p.url))};
}

// Discoverability works in either direction when two bios point to the same website.
export function pathBetween(edges, from, to, hidden = null) {
  const queue = [[from]], seen = new Set([from]);
  for (const path of queue) {
    const tail = path[path.length - 1];
    if (tail === to) return path;
    for (const edge of edges) {
      if (edge === hidden) continue;
      const next = edge.from === tail ? edge.to : edge.to === tail ? edge.from : null;
      if (next && !seen.has(next)) { seen.add(next); queue.push([...path, next]); }
    }
  }
  return null;
}
