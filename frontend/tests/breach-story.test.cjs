const test = require('node:test');
const assert = require('node:assert/strict');
const { breachStory, caseStory } = require('../scripts/breach-story');
const { article, index } = require('../scripts/build-breaches');
const { designArticle } = require('../scripts/article-story-design');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

test('scraped LinkedIn data is described as public data rather than a private-data breach', () => {
  const record = { Name: 'LinkedInScrape', Title: 'LinkedIn Scraped Data (2021)', BreachDate: '2021-04-08', AddedDate: '2021-10-02', PwnCount: 125698496, DataClasses: ['Email addresses', 'Usernames'], Description: 'Public profiles were scraped.', IsVerified: true };
  const html = article(record, '', [record]);
  assert.match(html, /<title>LinkedIn Public Profile Scrape \(2021\) \| MyRecon<\/title>/);
  assert.match(html, /public LinkedIn profile data was scraped and circulated/);
  assert.match(html, /125,698,496 unique email addresses/);
  assert.doesNotMatch(html, /LinkedIn Scraped Data \(2021\) was breached/);
  assert.doesNotMatch(html, /during which the data was already out|confirmed, active target|A handle links this account/);
  assert.match(html, /catalogue date does not establish when the data first became public/);
});

test('breach records label source dates and address counts without claiming article publication dates', () => {
  const record = {
    Name: 'ExampleCo', Title: 'ExampleCo', BreachDate: '2025-11-05',
    AddedDate: '2026-02-01T23:15:00Z', ModifiedDate: '2026-02-11T12:00:00Z',
    PwnCount: 1200, DataClasses: ['Email addresses', 'Names'],
  };
  const html = article(record, '', [record]);
  const schema = [...html.matchAll(/<script type="application\/ld\+json">([^<]+)<\/script>/g)]
    .map(([, data]) => JSON.parse(data)).find(data => data['@type'] === 'NewsArticle');
  assert.equal(schema.datePublished, undefined);
  assert.equal(schema.dateModified, undefined);
  assert.equal(schema.citation.url, 'https://haveibeenpwned.com/Breach/ExampleCo');
  assert.equal(schema.author.url, 'https://www.myrecon.xyz/about.html');
  assert.match(html, /Incident date in HIBP <time datetime="2025-11-05">5 November 2025<\/time>/);
  assert.match(html, /Added to HIBP <time datetime="2026-02-01">1 February 2026<\/time>/);
  assert.match(html, /HIBP record updated <time datetime="2026-02-11">11 February 2026<\/time>/);
  assert.match(html, /Have I Been Pwned lists 1,200 email addresses/);
  assert.doesNotMatch(article({ ...record, ModifiedDate: record.AddedDate }, '', [record]), /HIBP record updated/);
  assert.match(index([record], []), /One address can appear in more than one record/);
});

test('timeline enrichment preserves collection-specific email counts', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'myrecon-story-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const dir of ['scripts', 'content', 'assets/data', 'breaches']) fs.mkdirSync(path.join(root, dir), { recursive: true });
  fs.copyFileSync(path.join(__dirname, '../scripts/enrich-story-experience.js'), path.join(root, 'scripts/enrich-story-experience.js'));
  fs.copyFileSync(path.join(__dirname, '../content/editorial-photography.json'), path.join(root, 'content/editorial-photography.json'));
  fs.writeFileSync(path.join(root, 'assets/data/case-files.json'), JSON.stringify({ cases: [] }));
  const records = [
    { Name: 'AlienStealerLogs', Title: 'ALIEN TXTBASE Stealer Logs', slug: 'alienstealerlogs', PwnCount: 284132969, IsStealerLog: true, BreachDate: '2025-02-15', AddedDate: '2025-02-25', Description: 'Email addresses occurred in stealer logs.', DataClasses: ['Email addresses', 'Passwords'] },
    { Name: 'LinkedInScrape', Title: 'LinkedIn Scraped Data (2021)', slug: 'linkedinscrape', PwnCount: 125698496, BreachDate: '2021-04-08', AddedDate: '2021-10-02', Description: 'Public profiles were scraped.', DataClasses: ['Email addresses'] },
    { Name: 'ThePostMillennial', Title: 'The Post Millennial', slug: 'thepostmillennial', PwnCount: 56973345, BreachDate: '2024-05-02', AddedDate: '2024-05-10', Description: 'A breach and mailing lists were reported.', DataClasses: ['Email addresses'] },
  ];
  const feed = records.map(b => ({ name: b.Name, slug: b.slug, stealer_log: !!b.IsStealerLog, breach_date: b.BreachDate, added_date: b.AddedDate, story: breachStory(b) }));
  fs.writeFileSync(path.join(root, 'assets/data/breaches.json'), JSON.stringify({ breaches: feed }));
  for (const b of records) fs.writeFileSync(path.join(root, 'breaches', b.slug + '.html'), designArticle(article(b, '', [b]), `breaches/${b.slug}.html`));
  execFileSync(process.execPath, [path.join(root, 'scripts/enrich-story-experience.js')]);
  for (const b of records) {
    const html = fs.readFileSync(path.join(root, 'breaches', b.slug + '.html'), 'utf8');
    assert.match(html, /data-story-timeline/);
    assert.ok(html.includes(`href="https://haveibeenpwned.com/Breach/${b.Name}"`));
    assert.match(html, /email addresses are listed in the collection/);
    assert.doesNotMatch(html, /accounts are listed in this breach|during which the data was already out/);
    assert.match(html, /Behind the collected records/);
    assert.doesNotMatch(html, /Behind the exposed accounts|the whole point of a breach like this/);
  }
  const post = fs.readFileSync(path.join(root, 'breaches/thepostmillennial.html'), 'utf8');
  const logs = fs.readFileSync(path.join(root, 'breaches/alienstealerlogs.html'), 'utf8');
  assert.match(logs, /284,132,969 unique email addresses/);
  assert.match(logs, /HIBP record date/);
  assert.doesNotMatch(logs, /was breached|Accounts exposed|Reported breach date|population of/);
  assert.match(post, /mailing lists/);
  assert.doesNotMatch(post, /56,973,345 accounts were exposed/);
});
test('full breach story retains the ending and admits an unknown motive', () => {
  const text = 'In June the company discovered unauthorised access to its cloud service. ' + 'People had their contact information exposed. '.repeat(25) + 'The company notified its customers.';
  const story = breachStory({ Description: text, PwnCount: 10, DataClasses: ['Names'] });
  assert.ok(story.background.join(' ').includes('notified its customers'));
  assert.ok(story.background.length > 1);
  assert.ok(story.how.some(s => s.includes('unauthorised access')));
  assert.deepEqual(story.motive, []);
});
test('hypothetical extortion risk is not an incident motive', () => {
  const story = caseStory({ body: '<p>The company was breached.</p><h2>Protect yourself</h2><p>Medical detail in circulation invites extortion against people.</p>', vector: 'Unknown' });
  assert.deepEqual(story.motive, []);
});
test('published sale evidence keeps its qualifying wording', () => {
  const story = breachStory({ Description: 'The stolen records were reportedly posted for sale on a forum.' });
  assert.equal(story.motive[0], 'The stolen records were reportedly posted for sale on a forum.');
});
test('decimal counts stay intact and a company sale is not an attacker motive', () => {
  const story = caseStory({ body: '<p>A file of 5.4 million accounts was offered for sale.</p><h2>Later</h2><p>The company was sold for parts.</p>' });
  assert.equal(story.motive[0], 'A file of 5.4 million accounts was offered for sale.');
  assert.equal(story.motive.length, 1);
});

// AdSense low-value notice (2026-11-17): record-only archive entries must not
// be indexed. The scheduled job adds new HIBP records without a take.
test('breach entries without a substantial take are noindex', () => {
  const { MIN_TAKE_WORDS } = require('../scripts/build-breaches.js');
  const record = { Name: 'ExampleCo', Title: 'ExampleCo', BreachDate: '2026-01-01', AddedDate: '2026-02-01', PwnCount: 1000, DataClasses: ['Email addresses'], Description: 'ExampleCo suffered a data breach.', IsVerified: true };
  assert.match(article(record, '', [record]), /<meta name="robots" content="noindex, follow">/);
  assert.match(article(record, '<p>Short take.</p>', [record]), /noindex, follow/);
  const long = `<p>${'word '.repeat(MIN_TAKE_WORDS)}</p>`;
  assert.match(article(record, long, [record]), /<meta name="robots" content="index, follow">/);
});

// A lookup on a sensitive entry tells a stranger whether someone was on, for
// example, an adult site. HIBP restricts these to verified owners; so do we.
test('sensitive breach entries carry no email lookup', () => {
  const base = { Name: 'ExampleCo', Title: 'ExampleCo', BreachDate: '2026-01-01', AddedDate: '2026-02-01', PwnCount: 1000, DataClasses: ['Email addresses'], Description: 'ExampleCo suffered a data breach.', IsVerified: true };
  const sensitive = article({ ...base, IsSensitive: true }, '', [base]);
  assert.doesNotMatch(sensitive, /data-breach-check|id="bxEmail"|href="#bxEmail"/);
  assert.match(sensitive, /Why there is no email check on this page/);
  const ordinary = article(base, '', [base]);
  assert.match(ordinary, /data-breach-check/);
  assert.match(ordinary, /href="#bxEmail"/);
});
