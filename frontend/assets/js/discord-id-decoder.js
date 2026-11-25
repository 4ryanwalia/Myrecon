(() => {
  'use strict';
  const DISCORD_EPOCH = 1420070400000n;
  const form = document.getElementById('discord-id-form');
  if (!form || typeof BigInt !== 'function') return;
  const input = document.getElementById('discord-id-input');
  const out = document.getElementById('discord-id-result');

  const decode = (raw) => {
    const id = String(raw).trim();
    if (!/^\d{15,20}$/.test(id)) return { error: 'Enter a Discord ID: digits only, usually 17 to 20 of them.' };
    const value = BigInt(id);
    if (value >= (1n << 64n)) return { error: 'That number is too large to be a Discord ID.' };
    const ms = (value >> 22n) + DISCORD_EPOCH;
    const date = new Date(Number(ms));
    if (Number.isNaN(date.getTime()) || ms > BigInt(Date.now()) + 86400000n) {
      return { error: 'That number decodes to a date in the future, so it is not a valid Discord ID.' };
    }
    return {
      utc: date.toISOString().replace('T', ' ').replace('Z', ' UTC'),
      local: date.toLocaleString(undefined, { dateStyle: 'long', timeStyle: 'medium' }),
      worker: Number((value & 0x3E0000n) >> 17n),
      process: Number((value & 0x1F000n) >> 12n),
      increment: Number(value & 0xFFFn)
    };
  };

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const r = decode(input.value);
    out.textContent = '';
    if (r.error) {
      out.textContent = r.error;
      return;
    }
    const lines = [
      ['Created (UTC)', r.utc],
      ['Created (your time zone)', r.local],
      ['Internal worker / process / increment', `${r.worker} / ${r.process} / ${r.increment}`]
    ];
    const dl = document.createElement('dl');
    for (const [k, v] of lines) {
      const dt = document.createElement('dt');
      dt.textContent = k;
      const dd = document.createElement('dd');
      dd.textContent = v;
      dl.append(dt, dd);
    }
    out.append(dl);
  });
})();
