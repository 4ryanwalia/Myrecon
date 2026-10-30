const test = require('node:test');
const assert = require('node:assert/strict');
const { breachStory, caseStory } = require('../scripts/breach-story');
const { article } = require('../scripts/build-breaches');
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

test('timeline enrichment preserves collection-specific email counts', t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'myrecon-story-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const dir of ['scripts', 'content', 'assets/data', 'breaches']) fs.mkdirSync(path.join(root, dir), { recursive: true });
  fs.copyFileSync(path.join(__dirname, '../scripts/enrich-story-experience.js'), path.join(root, 'scripts/enrich-story-experience.js'));
  fs.copyFileSync(path.join(__dirname, '../content/editorial-photography.json'), path.join(root, 'content/editorial-photography.json'));
  fs.writeFileSync(path.join(root, 'assets/data/case-files.json'), JSON.stringify({ cases: [] }));
  const records = [
    { Name: 'LinkedInScrape', Title: 'LinkedIn Scraped Data (2021)', slug: 'linkedinscrape', PwnCount: 125698496, BreachDate: '2021-04-08', AddedDate: '2021-10-02', Description: 'Public profiles were scraped.', DataClasses: ['Email addresses'] },
    { Name: 'ThePostMillennial', Title: 'The Post Millennial', slug: 'thepostmillennial', PwnCount: 56973345, BreachDate: '2024-05-02', AddedDate: '2024-05-10', Description: 'A breach and mailing lists were reported.', DataClasses: ['Email addresses'] },
  ];
  const feed = records.map(b => ({ name: b.Name, slug: b.slug, breach_date: b.BreachDate, added_date: b.AddedDate, story: breachStory(b) }));
  fs.writeFileSync(path.join(root, 'assets/data/breaches.json'), JSON.stringify({ breaches: feed }));
  for (const b of records) fs.writeFileSync(path.join(root, 'breaches', b.slug + '.html'), designArticle(article(b, '', [b]), `breaches/${b.slug}.html`));
  execFileSync(process.execPath, [path.join(root, 'scripts/enrich-story-experience.js')]);
  for (const b of records) {
    const html = fs.readFileSync(path.join(root, 'breaches', b.slug + '.html'), 'utf8');
    assert.match(html, /data-story-timeline/);
    assert.match(html, /email addresses are listed in the collection/);
    assert.doesNotMatch(html, /accounts are listed in this breach|during which the data was already out/);
    assert.match(html, /Behind the collected records/);
    assert.doesNotMatch(html, /Behind the exposed accounts|the whole point of a breach like this/);
  }
  const post = fs.readFileSync(path.join(root, 'breaches/thepostmillennial.html'), 'utf8');
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
