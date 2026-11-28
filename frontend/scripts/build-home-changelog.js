const fs = require('node:fs');
const path = require('node:path');

const SLOT = /(<!-- latest-changelog:start -->)[\s\S]*?(<!-- latest-changelog:end -->)/;
const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const showDate = new Intl.DateTimeFormat('en-US', {
  year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
});

function escapeText(value) {
  return value.replace(/[&<>"']/g, char => ENTITIES[char]);
}

function buildHomeChangelog(root = path.resolve(__dirname, '..')) {
  const { entries } = JSON.parse(fs.readFileSync(path.join(root, 'data/changelog.json'), 'utf8'));
  const latest = [...entries].sort((a, b) => b.date.localeCompare(a.date))[0];
  if (!latest || !/^\d{4}-\d{2}-\d{2}$/.test(latest.date) || typeof latest.title !== 'string'
      || !Array.isArray(latest.changes) || !latest.changes.every(change => typeof change === 'string')) {
    throw new Error('Invalid homepage changelog entry');
  }

  const version = latest.version ? `<span class="changelog-version">${escapeText(latest.version)}</span>` : '';
  const date = showDate.format(new Date(latest.date + 'T12:00:00Z'));
  const changes = latest.changes.map(change => `                <li>${escapeText(change)}</li>`);
  const entry = [
    '',
    '          <ol class="changelog-list">',
    '            <li class="changelog-entry">',
    `              <div class="changelog-meta"><time datetime="${latest.date}">${date}</time>${version}<span class="changelog-latest">Latest update</span></div>`,
    `              <h3>${escapeText(latest.title)}</h3>`,
    '              <ul>',
    ...changes,
    '              </ul>',
    '            </li>',
    '          </ol>',
    '          ',
  ].join('\n');

  const file = path.join(root, 'index.html');
  const html = fs.readFileSync(file, 'utf8');
  if (!SLOT.test(html)) throw new Error('Homepage changelog slot is missing');
  const next = html.replace(SLOT, (_, start, end) => start + entry + end);
  if (html !== next) fs.writeFileSync(file, next);
}

if (require.main === module) buildHomeChangelog();
module.exports = { buildHomeChangelog };
