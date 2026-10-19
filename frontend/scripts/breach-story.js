/* Shared, source-derived reading sections for the website and Android feed. */
const plain = html => String(html || '').replace(/<[^>]*>/g, ' ')
  .replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ')
  .replace(/[\u2013\u2014]/g, ', ').replace(/\s+/g, ' ').trim();
const sentences = text => plain(text).split(/(?<=[.!?])\s+(?=[A-Z0-9"'“‘])/).filter(Boolean);
function paragraphs(text) {
  const result = [];
  let group = '';
  for (const sentence of sentences(text)) {
    if (group && (group + sentence).split(/\s+/).length > 70) { result.push(group); group = ''; }
    group += (group ? ' ' : '') + sentence;
  }
  if (group) result.push(group);
  return result.length ? result : [plain(text)].filter(Boolean);
}
const motivePattern = /extort|ransom|pay or leak|pay-or-leak|financially motivated|politically motivated|motive|motivation|(?:offered|posted|put|listed) for sale|sold (?:on|for)|selling (?:the|this|stolen)|demanded (?:a |\$)|demand(?:ing|ed).*shut/i;
const motiveEvidence = s => motivePattern.test(s) && !/\b(?:could|may|might|invites?|risk|expect|paying establishes|threatening disclosure)\b/i.test(s);
// A case can mention ransomware in background, advice or unrelated events.
// Only actual demands or attempts to sell the breached records support this
// section; a company being sold after a breach is not an attacker's motive.
const caseMotiveEvidence = s => motiveEvidence(s) && /ransom demand|demanded.{0,100}(?:ransom|payment|shut|close)|demand.{0,100}(?:shut down|closure)|(?:stolen|breach|dataset|records|accounts|user data).{0,100}(?:offered|posted|put|advertised).{0,80}sale|financially motivated|politically motivated|motive|motivation/i.test(s);
function breachStory(b, editorial) {
  const text = plain(b.Description);
  const mechanism = sentences(text).filter(s => /SQL injection|unsecured|unprotected|misconfigur|without authentication|unauthenticated|vulnerab|phishing|social engineering|credential stuffing|stolen credentials|information.steal|malware|scrap(?:ed|ing)|unauthori[sz]ed access|exposed (?:API|database)|compromised (?:credentials|account)/i.test(s));
  return {
    background: paragraphs(text),
    how: mechanism.length ? mechanism : [b.IsStealerLog
      ? "The records came from information-stealing malware on people's devices, rather than a single company database."
      : 'The published account does not explain the exact way the data was obtained.'],
    motive: sentences(text).filter(motiveEvidence).slice(0, 3),
    outcome: [`${Number(b.PwnCount || 0).toLocaleString('en-GB')} accounts are listed in this breach. This is a count of accounts, not necessarily individual people.`,
      (b.DataClasses || []).length ? `The reported exposed data includes ${b.DataClasses.join(', ')}.` : 'The source does not list the exposed fields.'],
    editorial: editorial ? paragraphs(editorial) : [],
  };
}
function caseStory(c) {
  const first = c.body.split(/<h2[^>]*>/i)[0];
  const sections = [...c.body.matchAll(/<h2[^>]*>(.*?)<\/h2>([\s\S]*?)(?=<h2|$)/gi)];
  const motive = sections.filter(s => /motive|motivation|why they|what they wanted/i.test(plain(s[1])));
  const aftermath = sections.filter(s => /aftermath|outcome|what happened next|what changed|consequences|settlement/i.test(plain(s[1])));
  const mechanism = sections.filter(s => /how |password decision|what went wrong|entry point|mechanism|weakness/i.test(plain(s[1])));
  const bodyParagraphs = [...c.body.matchAll(/<p[^>]*>([\s\S]*?)<\/p>/gi)].map(p => p[1]);
  return {
    background: paragraphs(first || c.description),
    how: [plain(c.vector || 'The public record does not establish the exact entry point.'), ...mechanism.flatMap(s => paragraphs(s[2])).slice(0, 2)],
    motive: c.motive ? paragraphs(c.motive) : motive.length ? motive.flatMap(s => paragraphs(s[2])) : bodyParagraphs.flatMap(sentences).filter(caseMotiveEvidence).slice(0, 2),
    outcome: [...(c.cost ? [plain(c.cost)] : []), ...aftermath.flatMap(s => paragraphs(s[2])).slice(0, 3),
      ...(c.records ? [`Reported scale: ${plain(c.records)}.`] : [])],
    details: sections.map(s => ({ title: plain(s[1]), paragraphs: [...s[2].matchAll(/<(?:p|li)\b[^>]*>([\s\S]*?)<\/(?:p|li)>/gi)].flatMap(p => paragraphs(p[1])) })),
  };
}
// Explicit identities for individual historical incidents. Composite campaigns
// and events without searchable email records intentionally have no target.
const caseNames = {
  'adobe-2013': ['Adobe'], 'dropbox-2012': ['Dropbox'], 'linkedin-2012': ['LinkedIn'],
  'rockyou-2009': ['RockYou'], 'myspace-2016': ['MySpace'], 'ashley-madison-2015': ['AshleyMadison'],
  '23andme-2023': ['23andMe'], 'british-airways-2018': ['BritishAirways'],
  'marriott-starwood-2018': ['Marriott'], 'medibank-2022': ['Medibank'],
  'optus-2022': ['Optus'], 'latitude-financial-2023': ['LatitudeFinancial'],
  'twitter-2022': ['Twitter200M'], 'att-2024': ['ATT'], 'star-health-2024': ['StarHealth'],
  'air-india-2021': ['AirIndia'], 'mobikwik-2021': ['MobiKwik'], 'vtech-2015': ['VTech'],
};
function caseTargets(c) {
  return (caseNames[c.slug] || []).map(name => ({ name, breach_date: c.sortDate, match_year: true }));
}
const unknownMotive = 'The published account does not establish the motive. We cannot tell what the attackers intended from the exposed data alone.';
module.exports = { plain, paragraphs, breachStory, caseStory, caseTargets, unknownMotive };
