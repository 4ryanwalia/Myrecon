import {caseFile, sourcePage, sourceUrl} from './mysteries.mjs';
const params = new URLSearchParams(location.search);
const c = /^\d+$/.test(params.get('case') || '') && caseFile(Number(params.get('case')));
const page = c && sourcePage(c, params.get('page'));
document.querySelector('#title').textContent = page?.title || 'Source unavailable';
if (page) {
  document.title = page.title + ' · MyRecon demo archive';
  document.querySelector('#body').textContent = page.body;
  document.querySelector('#detail').textContent = page.detail;
  for (const key of page.links) {
    const a = document.createElement('a');
    a.href = sourceUrl(c, key);
    a.textContent = sourcePage(c, key).title;
    document.querySelector('#related').append(a);
  }
}
