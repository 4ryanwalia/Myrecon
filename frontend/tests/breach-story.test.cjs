const test = require('node:test');
const assert = require('node:assert/strict');
const { breachStory, caseStory } = require('../scripts/breach-story');
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
