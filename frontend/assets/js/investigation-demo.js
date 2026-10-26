/* A separate, synthetic walkthrough. Never enters a live report or account storage. */
(() => {
  const host = document.querySelector('[data-investigation-demo]');
  if (!host) return;
  const steps = [
    { title: 'Start with a handle you remember.', text: 'In this fictional example, Sam remembers an old photography username. A search returns two possible profiles and one source that could not be checked.', detail: '<ul><li><b>Photo community</b><span>Public profile found</span></li><li><b>Discussion forum</b><span>Possible match</span></li><li><b>Gaming community</b><span>Check unavailable</span></li></ul>' },
    { title: 'Read the evidence before deciding.', text: 'The photo profile links to a website Sam controls. The forum only shares the username. Those are different strengths of evidence.', detail: '<div class="demo-evidence"><strong>Photo community → personal website</strong><p>A link you recognize gives you something to verify. A matching username by itself does not establish ownership.</p></div>' },
    { title: 'Which account can Sam confirm?', text: 'Sam recognizes the photo profile and can sign in to it. The forum remains uncertain.', detail: '<fieldset class="demo-choice"><legend>Choose an ownership label for the photo profile</legend><button type="button" data-demo-choice="mine">Mine</button><button type="button" data-demo-choice="unsure">Unsure</button><button type="button" data-demo-choice="not_mine">Not mine</button></fieldset><p data-demo-feedback role="status">Your selection stays inside this example.</p>' },
    { title: 'Leave with a next step.', text: 'For the account Sam confirms, the next step is to review public contact details and account security. If the account is no longer useful, read the service’s deletion instructions.', detail: '<div class="demo-evidence"><strong>Review → secure → keep or remove</strong><p>Record what you did. Recheck the source later. A timeout is not proof that an account was deleted.</p><a href="#tool">Check your own username →</a></div>' }
  ];
  let current = 0;
  const buttons = [...host.querySelectorAll('[data-demo-step]')];
  const render = () => {
    buttons.forEach((b, i) => b.setAttribute('aria-pressed', String(i === current)));
    const step = steps[current];
    host.querySelector('[data-demo-content]').innerHTML = `<span class="story-eyebrow">STEP ${current + 1} OF 4 · FICTIONAL EXAMPLE</span><h3>${step.title}</h3><p>${step.text}</p>${step.detail}`;
    host.querySelector('[data-demo-prev]').disabled = current === 0;
    host.querySelector('[data-demo-next]').textContent = current === 3 ? 'Start again' : 'Next step →';
  };
  host.addEventListener('click', e => {
    const step = e.target.closest('[data-demo-step]');
    if (step) { current = Number(step.dataset.demoStep); render(); }
    if (e.target.closest('[data-demo-prev]')) { current = Math.max(0, current - 1); render(); }
    if (e.target.closest('[data-demo-next]')) { current = (current + 1) % steps.length; render(); }
    const choice = e.target.closest('[data-demo-choice]');
    if (choice) {
      host.querySelectorAll('[data-demo-choice]').forEach(b => b.setAttribute('aria-pressed', String(b === choice)));
      host.querySelector('[data-demo-feedback]').textContent = choice.dataset.demoChoice === 'mine' ? 'Sam can confirm this account. Cleanup options belong here.' : 'Keep this account out of Sam’s cleanup list until ownership is confirmed.';
    }
  });
  host.querySelector('[data-demo-controls]').hidden = false;
  render();
})();
