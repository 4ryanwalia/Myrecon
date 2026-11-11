/* All variants occupy the same reserved slots; animation never changes layout. */
(() => {
  'use strict';
  const title = document.querySelector('.hero-rotating-title');
  if (!title) return;
  const slots = [...title.querySelectorAll('[data-hero-slot]')];
  const toggle = document.querySelector('.hero-rotate-toggle');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let index = 0, paused = false, visible = true, busy = false, timer = 0, revision = 0;
  const pending = new Set();
  function later(fn, delay) {
    const id = setTimeout(() => { pending.delete(id); fn(); }, delay);
    pending.add(id);
  }
  function settle() {
    revision++;
    for (const id of pending) clearTimeout(id);
    pending.clear();
    for (const slot of slots) {
      slot.classList.remove('is-rewriting');
      [...slot.children].forEach((word, i) => {
        word.classList.remove('is-leaving', 'is-entering');
        word.classList.toggle('is-current', i === index);
      });
    }
  }
  function rotate() {
    const next = (index + 1) % slots[0].children.length;
    const run = ++revision;
    slots.forEach((slot, row) => {
      const previous = slot.children[index], incoming = slot.children[next];
      later(() => {
        if (run !== revision) return;
        slot.classList.add('is-rewriting');
        previous.classList.add('is-leaving');
      }, row * 180);
      later(() => {
        if (run !== revision) return;
        previous.classList.remove('is-current', 'is-leaving');
        incoming.classList.add('is-current', 'is-entering');
      }, 260 + row * 180);
    });
    later(() => { index = next; settle(); }, 1360);
    timer = setTimeout(rotate, 6000);
  }
  function sync() {
    clearTimeout(timer);
    settle();
    if (toggle) toggle.hidden = motion.matches;
    if (motion.matches) {
      index = 0;
      settle();
    } else if (!paused && visible && !busy && !document.hidden) {
      timer = setTimeout(rotate, 5200);
    }
  }
  toggle?.addEventListener('click', () => {
    paused = !paused;
    toggle.setAttribute('aria-pressed', String(paused));
    const label = `${paused ? 'Resume' : 'Pause'} headline animation`;
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
    toggle.querySelector('path').setAttribute('d', paused ? 'm5 3 8 5-8 5z' : 'M4 3h3v10H4zm5 0h3v10H9z');
    sync();
  });
  document.addEventListener('focusin', event => {
    busy = !!event.target.closest?.('#tool,#results');
    sync();
  });
  document.addEventListener('focusout', () => {
    queueMicrotask(() => {
      const nextBusy = !!document.activeElement?.closest('#tool,#results');
      if (nextBusy !== busy) { busy = nextBusy; sync(); }
    });
  });
  new IntersectionObserver(entries => {
    const nextVisible = entries[0].isIntersecting;
    if (visible !== nextVisible) { visible = nextVisible; sync(); }
  }).observe(title);
  document.addEventListener('visibilitychange', sync);
  motion.addEventListener('change', sync);
  sync();
})();
