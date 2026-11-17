import {platforms, validHandle, checkProfile, discover, compareHandles, graph, pathBetween, webUrl} from './evidence.mjs';
import {puzzle} from './puzzle.mjs';
import {$, el, action, source, group} from './ui.mjs';

const lookup = $('#lookup'), compare = $('#compare-form'), output = $('#results');
const sessions = Object.fromEntries(['timeline', 'recognize', 'unlink', 'handles'].map(id => [id, {}]));
const accounts = new Map(), confirmed = new Set();
const renderPuzzle = puzzle($('#puzzle'));
const storageKey = 'myrecon.footprint.scrapbook.v1';
if (location.hostname === 'appassets.androidplatform.net') {
  const brand = $('.brand');
  brand.href = '/close';
  brand.textContent = '‹ Lookup';
}
let view, hiddenEdge = '', book = [], storageError = '';
function loadBook() {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey) || '[]');
    if (!Array.isArray(value)) throw new Error();
    book = value.filter(r => r && webUrl(r.url) && typeof r.title === 'string');
    storageError = '';
  } catch { storageError = 'Scrapbook storage is unavailable. Check your device or browser storage settings.'; }
}
function keep(row, remove = false) {
  loadBook();
  if (!storageError) {
    const next = book.filter(r => r.url !== row.url);
    if (!remove) {
      const {url, title, date, platform, handle, clue} = row;
      next.push({url, title, date, platform, handle, clue});
    }
    try { localStorage.setItem(storageKey, JSON.stringify(next)); book = next; }
    catch { storageError = 'Your scrapbook change could not be saved on this device.'; }
  }
  render();
}
const isSaved = row => book.some(r => r.url === row.url);
function keepButton(row) {
  return isSaved(row) ? action('Remove from scrapbook', () => keep(row, true), 'keep')
    : action('Save recognized find', () => keep(row));
}
function record(row) {
  const card = el('article', '', 'record');
  card.append(el('p', (row.date || 'Undated') + ' · ' + row.platform + ' · @' + row.handle, 'meta'),
    el('h3', row.title));
  if (row.clue && row.clue !== row.title) card.append(el('p', row.clue, 'muted'));
  card.append(group(source(row.url), keepButton(row)));
  return card;
}
function reports(session) {
  if (!session.reports) return;
  const box = el('details');
  const warnings = session.reports.filter(r => r.status.includes('inconclusive')).length;
  box.open = warnings > 0;
  box.append(el('summary', 'Source checks' + (warnings ? ' · ' + warnings + ' inconclusive' : '')));
  for (const r of session.reports) box.append(el('p', r.platform + ' · ' + r.status, 'muted'));
  output.append(box);
}
function recognition(s) {
  if (!s.cards?.length) return;
  const index = s.index;
  if (index === s.cards.length) {
    output.append(el('h2', 'Your recap'));
    if (!s.recognized.length) output.append(el('p', 'You left all of these clues unclaimed.'));
    for (const row of s.recognized) output.append(record(row));
    return;
  }
  const row = s.cards[index], card = el('article', '', 'card');
  card.append(el('p', 'Clue ' + (index + 1) + ' of ' + s.cards.length, 'meta'),
    el('h2', 'Recognize this?'), el('p', row.clue || row.title, 'clue'));
  if (s.answer === undefined) {
    card.append(group(action('I recognize it', () => { s.answer = true; render(); }, 'primary'),
      action('Unsure / skip', () => { s.answer = false; render(); })));
  } else {
    card.append(el('p', row.platform + ' · @' + row.handle + ' · ' + (row.date || 'Undated')),
      source(row.url, 'Reveal evidence ↗'));
    const advance = keepClue => {
      if (keepClue) s.recognized.push(row);
      s.index++; delete s.answer; render();
    };
    const next = index + 1 === s.cards.length ? 'View recap' : 'Next clue';
    card.append(group(action(s.answer ? 'Keep in recap' : next, () => advance(s.answer), 'primary')));
    if (s.answer) card.lastChild.append(action('Leave out', () => advance(false)));
  }
  output.append(card);
}
function simulation() {
  if (!accounts.size) return;
  output.append(el('h2', 'Which accounts are yours?'));
  const choices = el('div', '', 'checks');
  for (const p of accounts.values()) {
    const label = el('label'), input = el('input'); input.type = 'checkbox'; input.checked = confirmed.has(p.url);
    input.onchange = () => {
      if (input.checked) confirmed.add(p.url); else confirmed.delete(p.url);
      hiddenEdge = ''; render();
      output.querySelectorAll('.checks input')[[...accounts.keys()].indexOf(p.url)]?.focus();
    };
    label.append(input, p.platform + ' @' + p.handle);
    choices.append(group(label, source(p.url, 'Check profile ↗')));
  }
  output.append(choices);
  if (confirmed.size < 2) { output.append(el('p', 'Confirm at least two accounts to see the paths between them.', 'muted')); return; }
  const g = graph([...confirmed].map(key => accounts.get(key)));
  const box = el('div', '', 'card');
  output.append(box);
  box.append(el('h2', 'Simulate a link edit'), el('p', 'This uses public profile fields. Shared destinations can connect two profiles. Changes here only affect the simulation.'));
  if (!g.edges.length) { box.append(el('p', 'These profile fields contain no usable public links.')); return; }
  const label = el('label', 'Public link to hide', 'choice'), select = el('select');
  select.setAttribute('aria-label', 'Public link to hide');
  select.append(new Option('Show all links', ''));
  g.edges.forEach((edge, i) => select.append(new Option(g.nodes.get(edge.from) + ' · ' + edge.label + ' → ' + g.nodes.get(edge.to), String(i))));
  select.value = hiddenEdge;
  select.onchange = () => { hiddenEdge = select.value; render(); output.querySelector('select')?.focus(); };
  label.append(select); box.append(label);
  const hidden = hiddenEdge === '' ? null : g.edges[Number(hiddenEdge)];
  if (hidden) box.append(el('p', 'Simulated edit · remove the ' + hidden.label + ' link to ' +
    g.nodes.get(hidden.to) + ' on ' + g.nodes.get(hidden.from) + '.', 'summary'), source(hidden.source, 'Open the profile with this field ↗'));
  for (let i = 0; i < g.accounts.length; i++) {
    for (const b of g.accounts.slice(i + 1)) {
      const a = g.accounts[i], before = pathBetween(g.edges, a, b), after = pathBetween(g.edges, a, b, hidden);
      const pair = el('div', '', 'record compact');
      pair.append(el('h3', g.nodes.get(a) + ' and ' + g.nodes.get(b)));
      pair.append(el('p', after ? (hidden ? 'Still connected via ' : 'Visible path · ') + after.map(n => g.nodes.get(n)).join(' → ')
        : before ? 'Hiding this link breaks the last observed path between these accounts.' : 'No path in the public fields checked.'));
      box.append(pair);
    }
  }
  const evidence = el('details'); evidence.append(el('summary', 'Inspect the public links'));
  for (const edge of g.edges) evidence.append(group(source(edge.source, g.nodes.get(edge.from)), el('span', edge.label + ' →'), source(edge.target, g.nodes.get(edge.to))));
  box.append(evidence);
}
function comparison(s) {
  if (!s.rows) return;
  for (const handle of s.handles) {
    const card = el('article', '', 'card'); card.append(el('h2', '@' + handle));
    for (const r of s.rows.filter(r => r.handle === handle)) {
      const line = el('div', '', 'record compact');
      line.append(el('p', (r.handle === r.spelling ? 'Exact handle' : 'Similar spelling') + ' · @' + r.spelling + ' · ' + r.platform, 'meta'));
      if (r.row) line.append(source(r.row.url, r.handle === r.spelling ? 'Existing public use ↗' : 'Potential spelling confusion · open public use ↗'));
      else line.append(el('p', r.status === 'inconclusive' ? 'Inconclusive · the source could not confirm a result.' : 'No public profile returned.'));
      card.append(line);
    }
    output.append(card);
  }
}
function render() {
  const next = location.hash.slice(1);
  view = [...Object.keys(sessions), 'scrapbook', 'mystery'].includes(next) ? next : 'timeline';
  for (const section of document.querySelectorAll('#workspace > section')) section.hidden = section.id !== view;
  for (const a of document.querySelectorAll('.menu a, .saved-link')) {
    if (a.hash === '#' + view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  }
  const s = sessions[view] || {};
  lookup.hidden = !['timeline', 'recognize', 'unlink'].includes(view);
  $('#year-label').hidden = view !== 'timeline';
  lookup.elements.year.disabled = view !== 'timeline';
  $('#coverage').textContent = view === 'unlink' ? 'Only the selected public profile fields are checked.' :
    'Selected communities receive this handle. Each can return a profile and up to 30 public projects, articles or stories.';
  const button = $('#search-button');
  button.textContent = s.busy ? 'Checking sources…' : ({timeline: 'Find public traces', recognize: 'Find my clues', unlink: 'Find my profiles'}[view] || 'Search');
  button.disabled = Boolean(s.busy); compare.querySelector('button').disabled = Boolean(sessions.handles.busy);
  $('#count').textContent = book.length;
  $('#status').textContent = [s.message, storageError].filter(Boolean).join(' ');
  output.replaceChildren();
  if (view === 'mystery') { renderPuzzle(); return; }
  if (view === 'scrapbook') {
    if (!book.length) output.append(el('p', 'Your scrapbook is empty. Save a recognized find from the timeline or your game recap.', 'card'));
    for (const row of [...book].reverse()) output.append(record(row));
  } else if (view === 'unlink') { simulation(); reports(s); }
  else if (view === 'handles') comparison(s);
  else if (view === 'recognize') { recognition(s); reports(s); }
  else if (s.rows) {
    output.append(el('h2', 'Timeline for @' + s.handle));
    for (const row of s.rows) output.append(record(row));
    reports(s);
  }
}

lookup.elements.year.max = new Date().getUTCFullYear();
lookup.onsubmit = async event => {
  event.preventDefault();
  const mode = view, s = sessions[mode], handle = lookup.elements.handle.value.trim().replace(/^@/, '');
  if (!s || s.busy) return;
  if (!validHandle(handle)) { s.message = 'Enter a handle of 1–39 letters, numbers, dots, dashes or underscores, starting with a letter or number.'; render(); return; }
  const community = lookup.elements.community.value, selected = community ? [community] : platforms;
  const year = mode === 'timeline' ? lookup.elements.year.value : '';
  Object.assign(s, {busy: true, message: 'Checking public sources for @' + handle + '…', rows: null, reports: null, cards: null, handle});
  render();
  try {
    if (mode === 'unlink') {
      s.reports = await Promise.all(selected.map(async platform => ({platform, ...await checkProfile(platform, handle)})));
      for (const {row} of s.reports) if (row) accounts.set(row.url, row);
      s.message = s.reports.some(r => r.row) ? 'Review the profiles below.' : 'No public profiles returned for this handle. See the source checks.';
    } else {
      const data = await discover(handle, year, selected); Object.assign(s, data);
      s.message = s.rows.length ? '' : 'No matching traces were returned for these settings. See the source checks or try a different year.';
      if (mode === 'recognize') {
        const candidates = s.rows.filter(r => r.clue);
        // Interleave communities before selecting a short deck.
        const queues = selected.map(p => candidates.filter(r => r.platform === p));
        s.cards = [];
        while (s.cards.length < 5 && queues.some(q => q.length)) {
          for (const q of queues) if (q.length && s.cards.length < 5) s.cards.push(q.shift());
        }
        s.index = 0; s.recognized = []; delete s.answer;
        if (!s.cards.length) s.message = 'These sources returned no bio snippets or project titles to play with.';
      }
    }
  } catch { s.message = 'The lookup was interrupted. Try again.'; }
  finally { s.busy = false; render(); }
};
compare.onsubmit = async event => {
  event.preventDefault();
  const s = sessions.handles;
  if (s.busy) return;
  const data = new FormData(compare);
  const handles = [...new Set(['first','second','third'].map(n => data.get(n).trim().replace(/^@/, '')).filter(Boolean))];
  const selected = data.getAll('service');
  if (!selected.length || !handles.length || handles.some(h => !validHandle(h))) {
    s.message = 'Enter valid handles starting with a letter or number and select at least one platform.'; render(); return;
  }
  Object.assign(s, {handles, busy: true, rows: null, message: 'Checking exact names and nearby spellings…'}); render();
  try { s.rows = await compareHandles(handles, selected); s.message = 'Public uses for the selected names and spellings'; }
  catch { s.message = 'The comparison was interrupted. Try again.'; }
  finally { s.busy = false; render(); }
};
window.addEventListener('storage', e => { if (!e.key || e.key === storageKey) { loadBook(); render(); } });
window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
loadBook(); render();
