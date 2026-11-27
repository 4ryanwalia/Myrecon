// Discord ID lookup: decodes snowflake IDs in the browser. Nothing is sent to
// MyRecon or to Discord. Formulas are from Discord's developer reference
// ("Snowflakes", "Message Formatting", "Image Formatting"), read 28 Nov 2026:
//   timestamp ms = (id >> 22) + 1420070400000
//   default avatar index (new usernames) = (id >> 22) % 6
(() => {
  'use strict';
  if (typeof BigInt !== 'function') return;
  const EPOCH = 1420070400000n;
  const form = document.getElementById('discord-lookup-form');
  if (!form) return;
  const input = document.getElementById('discord-lookup-input');
  const compare = document.getElementById('discord-lookup-compare');
  const out = document.getElementById('discord-lookup-result');

  const STYLES = [
    ['t', 'Short time'], ['T', 'Medium time'], ['d', 'Short date'], ['D', 'Long date'],
    ['f', 'Long date, short time (default)'], ['F', 'Full date, short time'],
    ['s', 'Short date, short time'], ['S', 'Short date, medium time'], ['R', 'Relative time'],
  ];

  // Pull every ID out of what was pasted, with a label for what it most
  // likely is. A bare number could be a user, server, channel or message.
  const parse = (raw) => {
    const text = String(raw || '').trim();
    if (!text) return [];
    const link = text.match(/discord(?:app)?\.com\/channels\/(\d{15,20}|@me)\/(\d{15,20})(?:\/(\d{15,20}))?/i);
    if (link) {
      const found = [];
      if (link[1] !== '@me') found.push({ id: link[1], kind: 'Server' });
      found.push({ id: link[2], kind: link[1] === '@me' ? 'Direct message channel' : 'Channel' });
      if (link[3]) found.push({ id: link[3], kind: 'Message' });
      return found;
    }
    const patterns = [
      [/discord(?:app)?\.com\/users\/(\d{15,20})/i, 'User'],
      [/<@!?(\d{15,20})>/, 'User'],
      [/<@&(\d{15,20})>/, 'Role'],
      [/<#(\d{15,20})>/, 'Channel'],
      [/<a?:\w+:(\d{15,20})>/, 'Custom emoji'],
    ];
    for (const [re, kind] of patterns) {
      const m = text.match(re);
      if (m) return [{ id: m[1], kind }];
    }
    const digits = text.replace(/[\s,]/g, '');
    if (/^\d+$/.test(digits)) return [{ id: digits, kind: 'User, server, channel or message' }];
    return [{ error: 'Paste a Discord ID (digits only), a mention such as <@123...>, or a discord.com link.' }];
  };

  const decode = (id) => {
    if (!/^\d{15,20}$/.test(id)) return { error: `${id} is not a Discord ID: they are 15 to 20 digits long.` };
    const value = BigInt(id);
    if (value >= (1n << 64n)) return { error: 'That number is larger than 64 bits, so it is not a Discord ID.' };
    const ms = (value >> 22n) + EPOCH;
    if (ms > BigInt(Date.now()) + 86400000n) return { error: 'That number decodes to a date in the future, so it is not a valid Discord ID.' };
    const date = new Date(Number(ms));
    return {
      id,
      date,
      ms: Number(ms),
      unix: Number(ms / 1000n),
      avatarIndex: Number((value >> 22n) % 6n),
      worker: Number((value & 0x3E0000n) >> 17n),
      process: Number((value & 0x1F000n) >> 12n),
      increment: Number(value & 0xFFFn),
    };
  };

  const age = (fromMs, toMs = Date.now()) => {
    let days = Math.floor(Math.abs(toMs - fromMs) / 86400000);
    if (days < 1) {
      const hours = Math.floor(Math.abs(toMs - fromMs) / 3600000);
      return hours < 1 ? 'less than an hour' : `${hours} hour${hours === 1 ? '' : 's'}`;
    }
    const years = Math.floor(days / 365.2425);
    days -= Math.round(years * 365.2425);
    const months = Math.floor(days / 30.436875);
    days -= Math.round(months * 30.436875);
    const parts = [];
    if (years) parts.push(`${years} year${years === 1 ? '' : 's'}`);
    if (months) parts.push(`${months} month${months === 1 ? '' : 's'}`);
    if (days > 0 || !parts.length) parts.push(`${days} day${days === 1 ? '' : 's'}`);
    return parts.join(', ');
  };

  const el = (tag, attrs = {}, text) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const copyButton = (value) => {
    const btn = el('button', { type: 'button', class: 'discord-copy' }, 'Copy');
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(value);
        btn.textContent = 'Copied';
      } catch {
        btn.textContent = 'Select and copy';
      }
      setTimeout(() => { btn.textContent = 'Copy'; }, 1600);
    });
    return btn;
  };

  const card = (item) => {
    const r = decode(item.id);
    const box = el('section', { class: 'discord-card' });
    if (r.error) {
      box.append(el('p', { class: 'discord-error' }, r.error));
      return { box, r };
    }
    box.append(el('h3', {}, `${item.kind}: ${r.id}`));
    const dl = el('dl');
    const rows = [
      ['Created (UTC)', r.date.toISOString().replace('T', ' ').replace('Z', ' UTC')],
      ['Created (your time zone)', r.date.toLocaleString(undefined, { dateStyle: 'full', timeStyle: 'medium' })],
      ['Age', `${age(r.ms)} old`],
      ['Unix timestamp (seconds)', String(r.unix)],
      ['Worker / process / increment', `${r.worker} / ${r.process} / ${r.increment}`],
    ];
    for (const [k, v] of rows) dl.append(el('dt', {}, k), el('dd', {}, v));
    box.append(dl);

    if (/User/.test(item.kind)) {
      const fig = el('figure', { class: 'discord-avatar' });
      const img = el('img', {
        src: `https://cdn.discordapp.com/embed/avatars/${r.avatarIndex}.png`,
        alt: `Discord default avatar ${r.avatarIndex}`, width: '64', height: '64', loading: 'lazy',
      });
      const prefix = item.kind === 'User' ? '' : 'If this is a user ID: ';
      fig.append(img, el('figcaption', {}, `${prefix}default avatar ${r.avatarIndex}, what Discord shows if the user (on the new username system) has not set a picture.`));
      box.append(fig);
    }

    const table = el('table', { class: 'discord-stamps' });
    const head = el('tr');
    head.append(el('th', {}, 'Paste in Discord'), el('th', {}, 'Shows'), el('th', {}, ''));
    table.append(head);
    for (const [style, label] of STYLES) {
      const code = `<t:${r.unix}:${style}>`;
      const tr = el('tr');
      const td = el('td');
      td.append(el('code', {}, code));
      tr.append(td, el('td', {}, label), el('td', {}));
      tr.lastChild.append(copyButton(code));
      table.append(tr);
    }
    const details = el('details');
    details.append(el('summary', {}, 'Discord timestamp codes for this date'), table);
    box.append(details);
    return { box, r };
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    out.textContent = '';
    const first = parse(input.value);
    const second = compare && compare.value.trim() ? parse(compare.value) : [];
    if (!first.length) {
      out.append(el('p', { class: 'discord-error' }, 'Paste a Discord ID, mention or link first.'));
      return;
    }
    const decoded = [];
    for (const item of [...first, ...second]) {
      if (item.error) {
        out.append(el('p', { class: 'discord-error' }, item.error));
        continue;
      }
      const { box, r } = card(item);
      out.append(box);
      if (!r.error) decoded.push({ item, r });
    }
    if (first.length === 1 && second.length === 1 && decoded.length === 2) {
      const [a, b] = decoded;
      if (a.r.ms === b.r.ms) {
        out.prepend(el('p', { class: 'discord-verdict' }, 'Both IDs were created in the same millisecond.'));
      } else {
        const older = a.r.ms < b.r.ms ? a : b;
        const newer = older === a ? b : a;
        out.prepend(el('p', { class: 'discord-verdict' },
          `${older.r.id} is older. It was created ${age(older.r.ms, newer.r.ms)} before ${newer.r.id}.`));
      }
    }
  });

  // Prefill from a shared link such as /discord-id-lookup.html#175928847299117063.
  const hash = decodeURIComponent(location.hash.slice(1));
  if (/^\d{15,20}$/.test(hash)) {
    input.value = hash;
    form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true }));
  }
})();
