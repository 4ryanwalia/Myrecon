(() => {
  const form = document.querySelector('.directory-filter');
  if (!form) return;

  const query = form.querySelector('input');
  const clear = form.querySelector('button');
  const status = form.querySelector('[role="status"]');
  const categories = document.querySelector('.directory-jump');
  const normalize = text => text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
  const groups = [...document.querySelectorAll('.directory-section')].map(section => ({
    section,
    pages: [...section.querySelectorAll('.directory-item')].map(item => ({
      item,
      text: normalize(item.textContent + ' ' + item.querySelector('a').getAttribute('href')),
    })),
  }));
  const total = groups.reduce((count, group) => count + group.pages.length, 0);

  function filter() {
    const words = normalize(query.value).match(/[\p{L}\p{N}]+/gu) || [];
    let matches = 0;
    for (const { section, pages } of groups) {
      let groupMatches = 0;
      for (const { item, text } of pages) {
        const visible = words.every(word => text.includes(word));
        item.hidden = !visible;
        if (visible) groupMatches += 1;
      }
      section.hidden = groupMatches === 0;
      matches += groupMatches;
    }
    categories.hidden = words.length > 0;
    clear.disabled = query.value === '';
    const message = matches ? `${matches} of ${total} pages` : 'No pages match. Try fewer words.';
    if (status.textContent !== message) status.textContent = message;
  }

  query.addEventListener('input', filter);
  form.addEventListener('submit', event => {
    event.preventDefault();
    filter();
  });
  clear.addEventListener('click', () => {
    query.value = '';
    filter();
    query.focus();
  });
  form.hidden = false;
  filter();
})();
