const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const outcome = require('../assets/js/email-outcome.js');

test('multiple Google apps and overlapping profiles/signals count once per platform', () => {
  const data = {
    account_checks: { enabled: true },
    evidence_report: { profiles: [
      { platform: 'Google', basis: 'provider_email' },
      { platform: 'Google Maps', basis: 'provider_email' },
      { platform: 'YouTube', basis: 'provider_email' },
      { platform: 'GitHub', basis: 'historical_commit' },
    ], registrations: [{ service: 'Gmail', status: 'found' }, { service: 'Spotify', status: 'found' }] },
    linked_services: { services: [
      { service: 'google.com', kind: 'profile', basis: 'provider_email' },
      { service: 'Spotify', kind: 'registration' },
      { service: 'GitHub.com', kind: 'breach' },
    ] },
  };
  const result = outcome.platforms(data);
  assert.equal(result.total, 3);
  assert.equal(result.linked, 2);
  assert.equal(result.publicProfiles, 2);
  assert.equal(result.registrationSignals, 2);
  assert.equal(result.historical, 1);
  assert.deepEqual(result.names, ['Google', 'Spotify']);
  assert.deepEqual(result.allNames, ['GitHub', 'Google', 'Spotify']);
  assert.equal(result.lowerBound, true);
  assert.match(result.detail, /not the total number of accounts/);
});

test('historical and owner-declared links alone do not inflate linked-platform count', () => {
  const result = outcome.platforms({ evidence_report: { profiles: [
    { platform: 'GitHub', basis: 'historical_commit' },
    { platform: 'LinkedIn', basis: 'historical_public_link' },
    { platform: 'X', basis: 'public_link' },
  ] }, linked_services: { services: [{ service: 'Canva', kind: 'breach' }] } });
  assert.equal(result.linked, 0);
  assert.equal(result.total, 4);
  assert.equal(result.historicalOnly, 3);
  assert.equal(result.declared, 2);
});

test('a positive registration can coexist with historical evidence on the same platform', () => {
  const result = outcome.platforms({ evidence_report: { profiles: [{ platform: 'GitHub', basis: 'historical_commit' }] },
    registration_checks: { services: [{ service: 'GitHub.com', status: 'found' }, { service: 'Spotify', status: 'no_signal' }, { service: 'Zoom', status: 'timeout' }] } });
  assert.equal(result.linked, 1);
  assert.equal(result.historical, 1);
  assert.equal(result.historicalOnly, 0);
  assert.equal(result.total, 1);
});

test('the backend count contract remains authoritative and unknown platforms stay out of names', () => {
  const result = outcome.platforms({ platform_summary: { enabled: true,
    counts: { total_platforms: 2, linked_platforms: 1, historical_platforms: 1, historical_only_platforms: 1,
      public_profile_platforms: 1, registration_platforms: 1, owner_declared_platforms: 0 },
    platforms: [
      { id: 'google', name: 'Google', status: 'found', kinds: ['profile', 'registration'], basis: ['provider_email'], historical: false },
      { id: 'github', name: 'GitHub', status: 'found', kinds: ['profile'], basis: ['historical_commit'], historical: true },
      { id: 'zoom', name: 'Zoom', status: 'unknown', kinds: [], basis: [], historical: false },
    ], coverage: { attempted: 10, checked: 3, unknown: 7, skipped: 2, sources: [{ name: 'Google public profile', status: 'found' }] },
  } });
  assert.equal(result.total, 2);
  assert.equal(result.linked, 1);
  assert.deepEqual(result.names, ['Google']);
  assert.deepEqual(result.allNames, ['GitHub', 'Google']);
  assert.equal(result.coverage.completed, 3);
  assert.equal(result.coverage.unavailable, 7);
  assert.equal(result.coverage.status, 'incomplete');
});

test('new reports and older checked/off/unconfigured reports preserve their coverage gap', () => {
  const enabled = outcome.platforms({ account_checks: { enabled: true, sources: [{ name: 'GitHub', status: 'found' }] },
    registration_checks: { attempted: 3, checked: 1 }, profile_enrichment: { sources: [{ name: 'Rich profile provider', status: 'unconfigured' }] } });
  assert.equal(enabled.coverage.attempted, 4);
  assert.equal(enabled.coverage.completed, 2);
  assert.equal(enabled.coverage.unavailable, 2);
  assert.equal(enabled.coverage.unconfigured, 1);
  assert.equal(enabled.coverage.status, 'incomplete');
  assert.equal(outcome.platforms({ account_checks: { enabled: false } }).coverage.status, 'off');
  assert.equal(outcome.platforms({}).coverage.status, 'unknown');
});

test('invalid count metadata does not create invented totals or mutate a saved report', () => {
  const data = { platform_summary: { counts: { total_platforms: -2, linked_platforms: '100' },
    platforms: [{ id: 'spotify', name: 'Spotify', status: 'found', kinds: ['registration'], basis: [] }] } };
  const original = JSON.stringify(data);
  const result = outcome.platforms(data);
  assert.equal(result.total, 1);
  assert.equal(result.linked, 1);
  assert.equal(JSON.stringify(data), original);
  assert.equal(outcome.platforms(null).total, 0);
});

test('old linked account labels without provenance are not promoted to evidence', () => {
  assert.equal(outcome.platforms({ summary: { linked_accounts: ['Google', 'Zoom'] } }).linked, 0);
  const result = outcome.platforms({ github: { username: 'dev' }, gravatar: { exists: true } });
  assert.equal(result.linked, 1);
  assert.equal(result.historicalOnly, 1);
  assert.equal(outcome.platforms({ github: { status: 'rate_limited' } }).total, 0);
  assert.equal(outcome.platforms({ github: { status: 'no_match', username: 'stale' } }).total, 0);
  assert.equal(outcome.platforms({ evidence_report: { profiles: [{ platform: 'Unknown service' }] } }).linked, 0);
});

test('legacy provenance retains both historical and direct evidence without auxiliary key counts', () => {
  const result = outcome.platforms({ evidence_report: { profiles: [
    { platform: 'GitHub', basis: 'historical_commit', provenance: [{ basis: 'provider_email' }] },
    { platform: 'OpenPGP key', basis: 'provider_email' },
  ] }, linked_services: { services: [
    { service: 'Google', kind: 'profile', basis: 'provider_email', historical_evidence: [{ source: 'Breach provider' }] },
  ] } });
  assert.equal(result.total, 2);
  assert.equal(result.linked, 2);
  assert.equal(result.historical, 2);
  assert.equal(result.historicalOnly, 0);
});

test('review bodies, text and source-reported totals remain distinct', () => {
  const result = outcome.reviews({ source: 'Google profile source', reviews: [{ text: 'Review text' }, { rating: 4 }],
    stats: { Reviews: 8, Ratings: 2 }, review_source: 'Public review provider', review_coverage: { status: 'partial', total_reported: 8, returned: 2, limited: true } });
  assert.equal(result.returned, 2);
  assert.equal(result.textReturned, 1);
  assert.equal(result.totalReported, 8);
  assert.equal(result.source, 'Public review provider');
  assert.equal(result.state, 'limited');
  assert.equal(result.partial, true);
  assert.match(result.label, /2 review items returned · 8 source-reported/);
});

test('private, unavailable and unconfigured collections cannot become zero reviews', () => {
  for (const [status, state] of [['private', 'private'], ['unavailable', 'unavailable'], ['unconfigured', 'unconfigured'], ['authentication_required', 'unavailable']]) {
    const result = outcome.reviews({ reviews: [], stats: { Reviews: 5 }, review_coverage: { status } });
    assert.equal(result.state, state);
    assert.equal(result.totalReported, 5);
    assert.equal(result.partial, true);
    assert.doesNotMatch(result.label, /no public reviews/);
    assert.match(result.detail, /does not establish.*never posted a review/);
  }
});

test('an empty array with no completed source remains not returned, even if stats report zero', () => {
  assert.equal(outcome.reviews({ reviews: [] }).state, 'not_returned');
  assert.equal(outcome.reviews({ reviews: [], stats: { Reviews: 0 } }).state, 'not_returned');
  const completed = outcome.reviews({ reviews: [], review_coverage: { status: 'ok', total_reported: 0 } });
  assert.equal(completed.state, 'no_reviews');
  assert.equal(completed.partial, false);
  assert.match(completed.label, /^Source reports/);
});

test('a source with no total cannot turn successful empty results into a zero claim', () => {
  const result = outcome.reviews({ reviews: [], review_coverage: { status: 'ok' } });
  assert.equal(result.state, 'not_returned');
  assert.equal(result.totalReported, null);
  assert.match(result.detail, /did not provide a total review count/);
});

test('available review bodies survive an outage and retain source attribution', () => {
  const result = outcome.reviews({ reviews: [{ text: 'Already returned' }],
    review_coverage: { status: 'unavailable', source: 'Contributor source' } });
  assert.equal(result.state, 'found');
  assert.equal(result.returned, 1);
  assert.equal(result.partial, true);
  assert.equal(result.source, 'Contributor source');
  assert.match(result.detail, /coverage could not be verified/);
});

test('a retrieval cap does not imply the full review collection was collected', () => {
  const result = outcome.reviews({ reviews: [{ text: 'First' }, { text: 'Second' }],
    review_coverage: { status: 'ok', limit: 2 } });
  assert.equal(result.limited, true);
  assert.equal(result.totalReported, null);
  assert.equal(result.state, 'limited');
});

test('review coverage for a different contributor is ignored', () => {
  const data = { profile_enrichment: { sources: [
    { name: 'Google Maps public reviews', provider: 'Wrong provider', contributor_id: '22', status: 'ok', limit: 5 },
    { name: 'Google Maps public reviews', provider: 'Correct provider', contributor_id: '11', status: 'unavailable' },
  ] } };
  const result = outcome.reviews({ fields: { ID: '11' }, reviews: [] }, data);
  assert.equal(result.state, 'unavailable');
  assert.equal(result.limit, null);
  assert.equal(result.sources.length, 1);
  assert.match(result.source, /Correct provider/);
});

test('contradictory reported review counts preserve the provider value and mark partial', () => {
  const result = outcome.reviews({ reviews: [{ text: 'One' }, { text: 'Two' }],
    review_coverage: { status: 'ok', total_reported: 1, ratings_reported: 0 } });
  assert.equal(result.totalReported, 1);
  assert.equal(result.returned, 2);
  assert.equal(result.partial, true);
});

test('review totals exclude rating-only items so a complete mixed collection is not contradictory', () => {
  const result = outcome.reviews({ reviews: [{ text: 'One review' }, { text: 'Another review' }, { rating: 5 }],
    stats: { Reviews: 2, Ratings: 1 }, review_coverage: { status: 'ok', total_reported: 2, ratings_reported: 1 } });
  assert.equal(result.totalReported, 2);
  assert.equal(result.ratingsReported, 1);
  assert.equal(result.contributionsReported, 3);
  assert.equal(result.returned, 3);
  assert.equal(result.textReturned, 2);
  assert.equal(result.partial, false);
  assert.equal(result.state, 'found');
  assert.match(result.detail, /Source reports 2 reviews and 1 rating/);
});

test('the shipped browser global exposes both helpers without changing breach outcomes', () => {
  const context = { window: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/js/email-outcome.js'), 'utf8'), context);
  assert.equal(typeof context.window.MyReconEmailOutcome.platforms, 'function');
  assert.equal(typeof context.window.MyReconEmailOutcome.reviews, 'function');
  assert.equal(context.window.MyReconEmailOutcome({ summary: {} }).state, 'unavailable');
  assert.equal(context.window.MyReconEmailOutcome.reviews(null, null).state, 'not_returned');
});

function renderer() {
  const results = { innerHTML: '' };
  const context = {
    window: { MYRECON: { endpoints: {} }, MyReconEmailOutcome: outcome, matchMedia: () => ({ matches: true }) }, URL,
    location: { href: 'https://myrecon.xyz/' },
    document: { addEventListener() {}, querySelector: () => results, querySelectorAll: () => [] },
  };
  const source = fs.readFileSync(path.join(__dirname, '../assets/js/app.js'), 'utf8')
    .replace(/\}\)\(\);\s*$/, 'globalThis.adapter = { renderEmail, emailPlatformSummary, emailProfileCollections, buildTextSummary, exportData, toCSV };})();');
  vm.runInNewContext(source, context);
  return { api: context.adapter, results };
}
function completeReport() {
  const checked = { status: 'ok', checked: true, breached: false };
  return { query: { email: 'fixture@example.com' }, analysis: {}, summary: {}, breaches: checked, darkweb: checked,
    fallback: { status: 'skipped' }, account_checks: { enabled: true, sources: [] },
    evidence_report: { profiles: [], identity: {}, counts: {}, timeline: [], undated_events: [] } };
}

test('the real results renderer deduplicates linked platforms and excludes historical/declared chips', () => {
  const data = completeReport();
  data.evidence_report.profiles = [{ platform: 'Google', basis: 'provider_email' }, { platform: 'Gmail', basis: 'provider_email' },
    { platform: 'GitHub', basis: 'historical_commit' }, { platform: 'LinkedIn', basis: 'public_link' }];
  data.evidence_report.registrations = [{ service: 'YouTube', status: 'found' }];
  const { api, results } = renderer();
  const panel = api.emailPlatformSummary(data);
  assert.match(panel, /<h3>1 <span>linked platform<\/span>/);
  assert.match(panel, /Source-associated platforms[^>]*><span class="pill">Google<\/span>/);
  assert.doesNotMatch(panel, /<span class="pill">GitHub|<span class="pill">LinkedIn/);
  assert.match(panel, /Historical and declared links alone do not confirm a current account/);
  api.renderEmail(data);
  assert.match(results.innerHTML, /aria-label="Email linked platforms"/);
});

test('server linked flags control the rendered chips while inconclusive checks stay visible', () => {
  const data = completeReport();
  data.platform_summary = { enabled: true, counts: { total_platforms: 1, linked_platforms: 0, historical_platforms: 1 },
    platforms: [{ name: 'GitHub', status: 'found', kinds: ['profile'], basis: ['historical_commit'], linked: false, historical: true }],
    coverage: { checked: 1, attempted: 4, unknown: 3, sources: [] } };
  const { api } = renderer();
  const panel = api.emailPlatformSummary(data);
  assert.match(panel, /<h3>0 <span>linked platforms<\/span>/);
  assert.match(panel, /No linked-platform evidence was returned/);
  assert.match(panel, /1 of 4 platform checks completed · 3 could not establish an answer/);
  assert.doesNotMatch(panel, /aria-label="Source-associated platforms"/);
});

test('real Google review cards keep ratings, returned text, reported count and source separate', () => {
  const { api } = renderer();
  const profile = { platform: 'Google', source: 'Profile provider', stats: { Reviews: 5 },
    review_coverage: { status: 'partial', total_reported: 5, source: 'Review provider' },
    reviews: [{ name: 'Rating only', rating: 0 }, { name: 'Text item', text: 'Public review', rating: 4.5 }] };
  const html = api.emailProfileCollections(profile);
  assert.match(html, /2 items returned · 5 reviews reported by source/);
  assert.match(html, /1 returned item includes review text/);
  assert.match(html, /Review text not returned/);
  assert.match(html, /0 out of 5 stars/);
  assert.match(html, /Review provider/);
  assert.match(html, /collection is incomplete/);
  assert.doesNotMatch(html, /2 reviews found/);
});

test('real Google review availability distinguishes private/outage/configuration from no reviews', () => {
  const { api } = renderer();
  for (const [status, label] of [['private', 'Public reviews are inaccessible'], ['unavailable', 'Review source unavailable'], ['unconfigured', 'Review source is not connected']]) {
    const html = api.emailProfileCollections({ platform: 'Google', reviews: [], stats: { Reviews: 5 }, review_coverage: { status } });
    assert.match(html, new RegExp(label));
    assert.match(html, /Source reports 5 reviews/);
    assert.doesNotMatch(html, /no public reviews/);
  }
});

test('provider names, review bodies and URLs cannot inject markup into real results', () => {
  const { api } = renderer();
  const html = api.emailProfileCollections({ platform: 'Google', source: '<img src=x onerror=alert(1)>',
    review_coverage: { status: 'ok', total_reported: 1 }, reviews: [
      { name: '<script>alert(1)</script>', text: '<svg onload=alert(1)>', owner_reply: '<iframe src=x>',
        source_url: 'javascript:alert(1)', maps_url: 'data:text/html,bad', rating: 90 },
    ] });
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /&lt;svg/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<script>|<svg|<img|<iframe|href="javascript:|href="data:|90 out of 5 stars/);
  const platform = api.emailPlatformSummary({ platform_summary: { counts: { linked_platforms: 1 },
    platforms: [{ name: '<svg onload=alert(1)>', linked: true, status: 'found', kinds: ['profile'], basis: ['provider_email'], url: 'javascript:alert(1)' }] } });
  assert.match(platform, /&lt;svg/);
  assert.doesNotMatch(platform, /<svg|href="javascript:/);
});

test('copied summaries retain platform scope, review coverage and review source attribution', () => {
  const data = completeReport();
  data.evidence_report.profiles = [{ platform: 'Google', basis: 'provider_email', source: 'Google profile provider', reviews: [],
    review_coverage: { status: 'unavailable', total_reported: 8, source: 'Contributor review provider' } }];
  data.platform_summary = { enabled: true, counts: { total_platforms: 2, linked_platforms: 1, historical_platforms: 1 },
    platforms: [{ name: 'Google', status: 'found', kinds: ['profile'], basis: ['provider_email'], linked: true },
      { name: 'Canva', status: 'found', kinds: ['breach'], basis: ['historical_breach'], linked: false, historical: true }],
    coverage: { attempted: 3, checked: 1, unknown: 2 } };
  data.linked_services = { services: [{ service: 'Canva', kind: 'breach', evidence: 'Past breach association' }] };
  const { api } = renderer();
  const text = api.buildTextSummary({ tool: 'email', query: 'fixture@example.com', data });
  assert.match(text, /Linked platforms: 1; historical evidence: 1/);
  assert.match(text, /Platform coverage: 1 of 3 completed; 2 inconclusive/);
  assert.match(text, /Source-associated platforms: Google/);
  assert.match(text, /Google reviews: Review source unavailable/);
  assert.match(text, /Source reports 8 reviews/);
  assert.match(text, /Contributor review provider/);
  assert.doesNotMatch(text, /Linked services \(1\)/);
});

test('JSON and CSV exports preserve review collection state and platform counts', () => {
  const data = completeReport();
  data.evidence_report.profiles = [{ platform: 'Google', reviews: [], review_coverage: { status: 'private', total_reported: 5, source: 'Review provider' } }];
  data.platform_summary = { counts: { linked_platforms: 1 }, coverage: { checked: 1, attempted: 3, unknown: 2 }, platforms: [] };
  const { api } = renderer();
  const res = { tool: 'email', query: 'fixture@example.com', data };
  const exported = api.exportData(res);
  assert.equal(exported.evidence_report.profiles[0].review_coverage.status, 'private');
  assert.equal(exported.platform_summary.counts.linked_platforms, 1);
  assert.equal(exported.summary.coverage_incomplete, false);
  assert.equal(exported.summary.platform_coverage_incomplete, true);
  assert.equal(exported.summary.review_coverage_incomplete, true);
  const csv = api.toCSV(res);
  assert.match(csv, /"evidence_report.profiles\[0\]\.review_coverage.status","private"/);
  assert.match(csv, /"platform_summary.counts.linked_platforms","1"/);
});

test('completed platform and review coverage are exported without a false incomplete flag', () => {
  const data = completeReport();
  data.evidence_report.profiles = [{ platform: 'Google', reviews: [{ text: 'Review one' }, { text: 'Review two' }, { rating: 5 }],
    review_coverage: { status: 'ok', total_reported: 2, ratings_reported: 1, source: 'Review provider' } }];
  data.platform_summary = { enabled: true, counts: { linked_platforms: 1 }, coverage: { checked: 1, attempted: 1, unknown: 0 }, platforms: [] };
  const { api } = renderer();
  const exported = api.exportData({ tool: 'email', query: 'fixture@example.com', data });
  assert.equal(exported.summary.platform_coverage_incomplete, false);
  assert.equal(exported.summary.review_coverage_incomplete, false);
});

test('review and breach outages preserve separate platform coverage in exported reports', () => {
  const data = completeReport();
  data.partial = true;
  data.evidence_report.profiles = [{ platform: 'Google', reviews: [], review_coverage: { status: 'unavailable' } }];
  data.platform_summary = { enabled: true, status: 'ok', counts: { linked_platforms: 1 },
    coverage: { checked: 1, attempted: 1, unknown: 0, sources: [
      { name: 'Google public profile', status: 'found', scope: 'profiles' },
      { name: 'Google Maps public reviews', status: 'unavailable', scope: 'reviews' },
    ] }, platforms: [] };
  const { api } = renderer();
  const exported = api.exportData({ tool: 'email', query: 'fixture@example.com', data });
  assert.equal(exported.summary.platform_coverage_incomplete, false);
  assert.equal(exported.summary.review_coverage_incomplete, true);
  assert.equal(exported.summary.coverage_incomplete, true);
});
