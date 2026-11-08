// Article pages need navigation and theme controls, not the search application.
(() => {
  const root = document.documentElement;
  const themeButton = document.getElementById('themeToggle');
  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === 'light' ? '#f7f7f4' : '#111111';
    themeButton?.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  }
  let saved;
  try { saved = localStorage.getItem('myrecon-theme'); } catch {}
  applyTheme(['light', 'dark'].includes(saved) ? saved : root.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
  if (themeButton && !themeButton.dataset.themeBound) {
    themeButton.dataset.themeBound = '1';
    themeButton.addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem('myrecon-theme', next); } catch {}
    });
  }
  const button = document.getElementById('navToggle');
  const links = document.getElementById('navLinks');
  if (!button || !links) return;
  button.setAttribute('aria-controls', 'navLinks');
  if (!button.dataset.navBound) {
    button.dataset.navBound = '1';
    function setOpen(open) {
      links.classList.toggle('open', open);
      button.setAttribute('aria-expanded', String(open));
    }
    setOpen(false);
    button.addEventListener('click', () => setOpen(!links.classList.contains('open')));
    links.addEventListener('click', event => { if (event.target.closest('a')) setOpen(false); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && links.classList.contains('open')) { setOpen(false); button.focus(); }
    });
  }
})();
