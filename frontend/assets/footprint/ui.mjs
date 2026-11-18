export const $ = selector => document.querySelector(selector);
export function el(tag, text = '', cls = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
export function action(text, run, cls) {
  const b = el('button', text, cls);
  b.type = 'button';
  b.addEventListener('click', run);
  return b;
}
export function source(url, label = 'Open evidence ↗') {
  const a = el('a', label);
  a.href = url;
  a.target = '_blank';
  a.rel = 'noreferrer noopener';
  return a;
}
export function group(...children) {
  const node = el('div', '', 'actions');
  node.append(...children);
  return node;
}
