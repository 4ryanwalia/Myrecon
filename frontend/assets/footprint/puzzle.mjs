import {edition, provesAnswer, sourcePage, sourceUrl, publicBase} from './mysteries.mjs';
import {el, action, source, group} from './ui.mjs';

export function puzzle(container) {
  let c, start, seconds, selected, proof, reading, feedback, shared;
  const format = n => Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');

  async function share() {
    const url = publicBase + '/footprint?week=' + c.week + '#mystery';
    const text = 'I solved the MyRecon username mystery in ' + format(seconds) + '.';
    try {
      if (navigator.share) { await navigator.share({title: 'MyRecon weekly mystery', text, url}); return; }
      await navigator.clipboard.writeText(text + ' ' + url);
      shared = 'Copied time and puzzle link.';
    } catch (err) {
      if (err.name === 'AbortError') return;
      shared = text + ' ' + url;
    }
    render();
  }

  function read(page) { reading = page; render(); container.querySelector('.proof')?.focus(); }

  function render() {
    const current = edition(new Date(), new URLSearchParams(location.search).get('week'));
    if (!c || (!start && current.week !== c.week)) c = current;
    const card = el('div', '', 'card');
    container.replaceChildren(card);
    card.append(el('p', 'Week of ' + c.week + ' · Two-minute puzzle', 'meta'),
      el('h2', 'Who made ' + c.title + '?'),
      el('p', 'Two profiles use @' + c.handle + '. Which studio created the ' + c.kind + '?'));
    if (seconds !== undefined) {
      card.append(el('p', 'Solved in ' + format(seconds), 'clue'),
        el('p', c.studios[c.maker] + ' is credited for ' + c.roles[c.maker].toLowerCase() + '.'),
        group(source(sourceUrl(c, c.proofPage), 'Read the ' + c.proofTitle + ' ↗'), action('Share my time', share, 'primary')));
      if (shared) card.append(el('p', shared, 'muted'));
      return;
    }
    if (!start) {
      card.append(group(action('Start mystery', () => { start = performance.now() || 1; render(); }, 'primary')));
      return;
    }
    card.append(group(...['a', 'b'].map((key, i) => action(c.studios[i] + ' profile', () => read(key)))));
    if (reading) {
      const page = sourcePage(c, reading);
      const article = el('article', '', 'card proof');
      article.tabIndex = -1;
      article.append(el('p', 'MyRecon demo archive', 'kicker'), el('h3', page.title),
        el('p', page.body), el('p', page.detail),
        group(...page.links.map(key => action(sourcePage(c, key).title, () => read(key)))),
        group(source(sourceUrl(c, reading), 'Open public source ↗'), action('Use this source', () => {
          proof = sourceUrl(c, reading); feedback = ''; render(); container.querySelector('input[name=proof]').focus();
        })));
      card.append(article);
    }
    const form = el('form');
    const label = el('label', 'Which profile made it?', 'choice');
    const select = el('select'); select.required = true; select.setAttribute('aria-label', 'Which profile made it?');
    select.append(new Option('Choose a studio', ''), ...c.studios.map((s, i) => new Option(s, i)));
    select.value = selected ?? ''; select.onchange = () => { selected = select.value; };
    label.append(select);
    const cite = el('label', 'Source that proves your answer', 'choice');
    const input = el('input'); input.type = 'url'; input.name = 'proof'; input.required = true;
    input.placeholder = 'Choose a source above or paste its URL'; input.value = proof || '';
    input.oninput = () => { proof = input.value.trim(); }; cite.append(input);
    const submit = el('button', 'Submit answer', 'primary');
    form.append(label, cite, submit);
    form.onsubmit = event => {
      event.preventDefault();
      if (provesAnswer(c, select.value, input.value.trim())) {
        seconds = Math.max(1, Math.round((performance.now() - start) / 1000));
      } else feedback = 'Look for the page that credits a specific studio for making the project. Check both your studio and your source.';
      render();
    };
    card.append(form);
    if (feedback) { const message = el('p', feedback, 'summary'); message.setAttribute('role', 'status'); card.append(message); }
  }
  return render;
}
