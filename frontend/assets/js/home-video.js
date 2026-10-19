/* Load the external player only after the visitor chooses to watch. */
(() => {
  const frame = document.querySelector('[data-home-video]');
  const play = frame?.querySelector('[data-home-video-play]');
  if (!play) return;

  play.removeAttribute('target');
  play.setAttribute('role', 'button');
  play.addEventListener('keydown', (event) => {
    if (event.key === ' ') {
      event.preventDefault();
      play.click();
    }
  });
  play.addEventListener('click', (event) => {
    event.preventDefault();
    const player = document.createElement('iframe');
    player.src = 'https://www.youtube-nocookie.com/embed/JysZLBTrdc4?autoplay=1&playsinline=1&rel=0';
    player.title = 'MyRecon product video';
    player.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    player.allowFullscreen = true;
    player.referrerPolicy = 'strict-origin-when-cross-origin';
    player.tabIndex = 0;
    frame.replaceChildren(player);
    player.focus();
  });

  // Stop playback when the search interface hides the homepage sections.
  new MutationObserver(() => {
    if (document.body.classList.contains('tool-mode') && frame.querySelector('iframe')) {
      frame.replaceChildren(play);
    }
  }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
})();
