export const publicBase = 'https://www.myrecon.xyz';
export const sourcePath = '/assets/footprint/source.html';

// Each edition has two first-party demo profiles and two independently addressable source pages.
const editions = [
  ['orbitfox', 'Moon Orchard', 'game', 'Lantern Studio', 'Night Arcade', 'A puzzle gardener collecting tiny worlds.', 'I record soundscapes for games.', 'Game design and programming', 'Field recordings', 0],
  ['paperfin', 'Tidal Atlas', 'zine', 'Print Room', 'Dock Notes', 'A shelf of hand-bound things.', 'I draw coastlines from old maps.', 'Cover printing', 'Writing and illustration', 1],
  ['softrelay', 'Pocket Weather', 'instrument', 'Bench Notes', 'Wave Club', 'Solder, switches and small enclosures.', 'I play modular sets on rainy evenings.', 'Circuit design and assembly', 'Demo performance', 0],
  ['emberloop', 'Lantern Walk', 'photo essay', 'Darkroom', 'Field Desk', 'I edit prints and mix my own developer.', 'My camera goes everywhere on foot.', 'Print preparation', 'Photography and text', 1],
  ['mintbyte', 'Glass Ferry', 'short film', 'Frame Room', 'Splice Club', 'A notebook of miniature film sets.', 'I collect the sounds of city ferries.', 'Direction and animation', 'Location sound', 0],
  ['inkmoth', 'Paper Constellations', 'typeface', 'Press Club', 'Glyph House', 'I test new letters on our old press.', 'I draw letters on squared paper.', 'Specimen printing', 'Typeface design', 1],
  ['copperowl', 'Signal Garden', 'radio play', 'Attic Radio', 'Copper Stage', 'I write late-night radio stories.', 'I build objects that make strange sounds.', 'Script and direction', 'Foley effects', 0],
  ['mossframe', 'North Window', 'board game', 'Token Room', 'Table Guild', 'Hand-painted pieces for crowded tables.', 'I make games that fit in a coat pocket.', 'Token painting', 'Game design', 1],
];
const evidencePages = [
  ['credits', 'release credits'], ['colophon', 'inside-back-cover colophon'],
  ['schematic', 'schematic title block'], ['contact-sheet', 'contact sheet notes'],
  ['end-titles', 'end titles'], ['specimen', 'type specimen imprint'],
  ['programme', 'broadcast programme'], ['rulebook', 'rulebook acknowledgments'],
];
const weekMs = 7 * 86400000;
const epoch = Date.UTC(2026, 10, 16);
export function edition(now = new Date(), requested = '') {
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const monday = today - ((now.getUTCDay() + 6) % 7) * 86400000;
  const wanted = /^\d{4}-\d{2}-\d{2}$/.test(requested) ? Date.parse(requested + 'T00:00:00Z') : NaN;
  const start = wanted >= epoch && wanted <= monday && (wanted - epoch) % weekMs === 0 ? wanted : monday;
  const index = ((Math.floor((start - epoch) / weekMs) % editions.length) + editions.length) % editions.length;
  return {...caseFile(index), week: new Date(start).toISOString().slice(0, 10)};
}

export function caseFile(index) {
  if (!Number.isInteger(index) || !editions[index]) return null;
  const [handle, title, kind, a, b, bioA, bioB, roleA, roleB, maker] = editions[index];
  const [proofPage, proofTitle] = evidencePages[index];
  return {index, handle, title, kind, studios: [a, b], bios: [bioA, bioB], roles: [roleA, roleB], maker, proofPage, proofTitle};
}
export function sourceUrl(c, page) {
  return publicBase + sourcePath + '?case=' + c.index + '&page=' + page;
}
export function sourcePage(c, page) {
  if (page === 'a' || page === 'b') {
    const i = page === 'a' ? 0 : 1;
    return {title: c.studios[i] + ' / @' + c.handle, body: c.bios[i],
      detail: 'On my workbench this season · ' + c.title, links: i === c.maker ? [c.proofPage, 'journal'] : ['journal']};
  }
  if (page === 'journal') return {title: c.title + ' · studio journal',
    body: 'Both ' + c.studios.join(' and ') + ' contributed to the ' + c.kind + '.',
    detail: 'Find each contributor’s role in the ' + c.proofTitle + '.', links: [c.proofPage]};
  if (page === c.proofPage) return {title: c.title + ' · ' + c.proofTitle,
    body: c.roles[0] + ' — ' + c.studios[0] + ' / @' + c.handle,
    detail: c.roles[1] + ' — ' + c.studios[1] + ' / @' + c.handle, links: ['a', 'b']};
  return null;
}
export function provesAnswer(c, studio, raw) {
  try {
    const u = new URL(raw);
    return studio === String(c.maker) && u.origin === publicBase && u.pathname === sourcePath &&
      u.searchParams.get('case') === String(c.index) && u.searchParams.get('page') === c.proofPage;
  } catch { return false; }
}
