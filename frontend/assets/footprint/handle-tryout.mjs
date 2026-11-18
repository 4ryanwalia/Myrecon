import {nearby, validHandle, webUrl} from './evidence.mjs';
import {$, el, source} from './ui.mjs';

const api = '/api/handle-tryout/';
const pageSize = 20;
const labels = {found: 'Public use', not_found: 'No public profile returned', unknown: 'Inconclusive', unchecked: 'Unchecked'};

// Check each spelling once, even if it is both a proposed name and a variant.
function spellingsFor(handles, similar) {
  const spellings = new Map(handles.map(h => [h, []]));
  if (similar) for (const handle of handles) {
    for (const spelling of nearby(handle)) {
      if (!spellings.has(spelling)) spellings.set(spelling, []);
      spellings.get(spelling).push(handle);
    }
  }
  return spellings;
}

function orderedResults(payload, handle, names) {
  if (payload?.status !== 'ok' || payload.handle !== handle || !Array.isArray(payload.results) ||
      payload.results.length !== names.length) throw new Error('Incomplete platform response.');
  const rows = new Map(payload.results.map(r => [r?.platform, r]));
  return names.map(platform => {
    const row = rows.get(platform);
    if (!row || !Object.hasOwn(labels, row.verdict) || typeof row.reason !== 'string' ||
        (row.verdict === 'found' && !webUrl(row.url))) throw new Error('Invalid platform response.');
    return {...row, spelling: handle};
  });
}

function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const cancel = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', cancel); resolve(); }, ms);
    signal.addEventListener('abort', cancel, {once: true});
  });
}

async function fetchBatch(handle, platforms, signal, notify) {
  for (let attempt = 0; ; attempt++) {
    const response = await fetch(api + 'check', {method: 'POST', signal: AbortSignal.any([signal, AbortSignal.timeout(90000)]), credentials: 'omit',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({handle, platforms})});
    if (response.ok) return orderedResults(await response.json(), handle, platforms);
    if (![429, 503].includes(response.status) || attempt >= 3) throw new Error('Checker unavailable.');
    const seconds = Math.max(1, Number(response.headers.get('Retry-After')) || 5);
    notify('The checker is busy. Retrying in ' + seconds + ' seconds…');
    await delay(seconds * 1000, signal);
  }
}

export function handleTryout() {
  const form = $('#compare-form'), picker = $('#platform-picker'), submit = $('#compare-button');
  const status = $('#tryout-status'), filter = $('#tryout-outcome'), query = $('#tryout-search');
  const search = $('#platform-search'), list = $('#platform-list');
  let catalog, loading = false, selected = new Set(), run, controller, page = 0;

  function selectionCount() {
    $('#platform-count').textContent = selected.size + ' of ' + catalog.platforms.length + ' platforms selected';
    submit.disabled = !selected.size || Boolean(controller);
  }

  function showChoices() {
    const term = search.value.trim().toLowerCase();
    const choices = catalog.platforms.filter(p => (p.name + ' ' + p.category).toLowerCase().includes(term));
    const fragment = document.createDocumentFragment();
    for (const p of choices) {
      const label = el('label'), input = el('input');
      input.type = 'checkbox'; input.value = p.name; input.checked = selected.has(p.name);
      label.append(input, p.name); fragment.append(label);
    }
    if (!choices.length) fragment.append(el('p', 'No platforms match your search.', 'muted'));
    list.replaceChildren(fragment);
  }

  async function load() {
    if (catalog || loading) return;
    loading = true;
    $('#platform-count').textContent = 'Loading platform catalog…';
    $('#catalog-retry').hidden = true;
    try {
      const response = await fetch(api + 'platforms', {credentials: 'omit', signal: AbortSignal.timeout(60000)});
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (data.status !== 'ok' || !data.platforms?.length || !Array.isArray(data.popular) ||
          !Number.isSafeInteger(data.batchSize) || data.batchSize < 1) throw new Error();
      const ranks = new Map(data.popular.map((name, index) => [name, index]));
      data.platforms.sort((a, b) => (ranks.get(a.name) ?? Infinity) - (ranks.get(b.name) ?? Infinity) ||
        a.name.localeCompare(b.name));
      catalog = data;
      selected = new Set(catalog.platforms.map(p => p.name));
      picker.hidden = false; selectionCount();
    } catch {
      $('#platform-count').textContent = 'The platform catalog could not be loaded.';
      $('#catalog-retry').hidden = false;
    } finally { loading = false; }
  }
  $('#catalog-retry').onclick = load;
  picker.ontoggle = () => { if (picker.open && catalog) showChoices(); };
  search.oninput = showChoices;
  search.onkeydown = event => { if (event.key === 'Enter') event.preventDefault(); };
  list.onchange = e => {
    if (e.target.checked) selected.add(e.target.value); else selected.delete(e.target.value);
    selectionCount();
  };
  function choose(names) { selected = new Set(names); selectionCount(); showChoices(); }
  $('#pick-all').onclick = () => choose(catalog.platforms.map(p => p.name));
  $('#pick-popular').onclick = () => choose(catalog.popular);
  $('#pick-none').onclick = () => choose([]);

  function showResults() {
    const rows = run.rows, total = run.names.length * run.spellings.size;
    const counts = {found: 0, not_found: 0, unknown: 0, unchecked: 0};
    for (const r of rows) counts[r.verdict]++;
    $('#tryout-title').textContent = run.handles.map(h => '@' + h).join(' · ');
    $('#tryout-progress').max = total; $('#tryout-progress').value = rows.length;
    $('#tryout-counts').textContent = rows.length + ' of ' + total + ' results · ' + counts.found + ' public uses · ' +
      counts.not_found + ' with no public profile · ' + counts.unknown + ' inconclusive · ' +
      counts.unchecked + ' unchecked' + (rows.length < total ? ' · ' + (total - rows.length) + ' pending' : '');
    $('#tryout-stop').hidden = !controller;
    $('#tryout-resume').hidden = Boolean(controller) || run.index >= run.batches.length;
    const term = query.value.trim().toLowerCase().replace(/^@/, '');
    const matches = rows.filter(r => (r.platform + ' ' + r.spelling).toLowerCase().includes(term));
    const visible = filter.value ? matches.filter(r => r.verdict === filter.value)
      : [...matches.filter(r => r.verdict === 'found'), ...matches.filter(r => r.verdict !== 'found')];
    const pages = Math.ceil(visible.length / pageSize);
    page = Math.min(page, Math.max(0, pages - 1));
    const fragment = document.createDocumentFragment();
    for (const r of visible.slice(page * pageSize, (page + 1) * pageSize)) {
      const line = el('div', '', 'record compact'), similarTo = run.spellings.get(r.spelling);
      line.append(el('h3', r.platform + ' · @' + r.spelling));
      if (similarTo.length) line.append(el('p', (r.verdict === 'found' ? 'Potential spelling confusion for ' : 'Similar spelling of ') +
        similarTo.map(h => '@' + h).join(', '), 'meta'));
      if (r.verdict === 'found') line.append(source(webUrl(r.url), 'Open public profile ↗'));
      else line.append(el('p', labels[r.verdict] + ' · ' + r.reason, 'muted'));
      fragment.append(line);
    }
    if (!visible.length) fragment.append(el('p', rows.length ? 'No returned results match this filter.' : 'Waiting for the first results…', 'muted'));
    $('#tryout-rows').replaceChildren(fragment);
    $('#tryout-pages').hidden = pages < 2;
    $('#tryout-page').textContent = (page + 1) + ' of ' + pages;
    $('#tryout-prev').disabled = page === 0; $('#tryout-next').disabled = page + 1 >= pages;
  }

  async function execute() {
    if (controller) return;
    controller = new AbortController();
    const signal = controller.signal;
    selectionCount(); showResults();
    try {
      for (; run.index < run.batches.length; run.index++) {
        const {handle, names} = run.batches[run.index];
        status.textContent = 'Checking @' + handle + ' · ' + names[0] + (names.length > 1 ? ' and ' + (names.length - 1) + ' more…' : '…');
        const rows = await fetchBatch(handle, names, signal, message => { status.textContent = message; });
        run.rows.push(...rows); showResults();
      }
      status.textContent = 'Comparison complete.';
    } catch {
      status.textContent = signal.aborted ? 'Comparison stopped. Your completed results are below.'
        : 'The comparison was interrupted. Resume to continue from the last completed batch.';
    } finally { controller = null; selectionCount(); showResults(); }
  }
  form.onsubmit = event => {
    event.preventDefault();
    if (!catalog || controller) return;
    const handles = [...new Set(['first', 'second', 'third'].map(key => form.elements[key].value.trim().replace(/^@/, '')).filter(Boolean))];
    if (!handles.length || handles.some(h => !validHandle(h)) || !selected.size) {
      status.textContent = 'Enter names of 1–39 letters, numbers, dots, dashes or underscores, starting with a letter or number. Select at least one platform.';
      return;
    }
    const spellings = spellingsFor(handles, form.elements.similar.checked);
    const names = catalog.platforms.map(p => p.name).filter(p => selected.has(p)), batches = [];
    // Compare the same group of platforms across the proposed names first.
    for (const group of [handles, [...spellings.keys()].filter(h => !handles.includes(h))]) {
      for (let i = 0; i < names.length; i += catalog.batchSize) {
        const slice = names.slice(i, i + catalog.batchSize);
        for (const handle of group) batches.push({handle, names: slice});
      }
    }
    run = {handles, spellings, names, batches, index: 0, rows: []};
    page = 0; filter.value = ''; query.value = ''; $('#tryout-report').hidden = false; execute();
  };
  $('#tryout-stop').onclick = () => controller?.abort();
  $('#tryout-resume').onclick = execute;
  filter.onchange = () => { page = 0; showResults(); };
  query.oninput = () => { page = 0; showResults(); };
  $('#tryout-prev').onclick = () => { page--; showResults(); };
  $('#tryout-next').onclick = () => { page++; showResults(); };
  return load;
}
