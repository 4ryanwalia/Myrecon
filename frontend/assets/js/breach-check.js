/* Check in place; never put an email in the page URL, analytics or storage. */
(function () {
  'use strict';
  document.querySelectorAll('[data-breach-check]').forEach(function (form) {
    var result = form.querySelector('.bx-check-result');
    var input = form.querySelector('input[type="email"]');
    var button = form.querySelector('button[type="submit"]');
    var running = false;
    input.addEventListener('input', function () { result.hidden = true; result.textContent = ''; });
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (running || !form.reportValidity()) return;
      var targets;
      try { targets = JSON.parse(form.dataset.targets || '[]'); }
      catch (_) { targets = []; }
      result.hidden = false;
      if (!targets.length) {
        result.dataset.state = 'unsupported';
        result.textContent = 'An email check is not available for this incident. Some events do not have searchable email records.';
        return;
      }
      running = true;
      button.disabled = true;
      input.readOnly = true;
      form.setAttribute('aria-busy', 'true');
      result.dataset.state = 'loading';
      result.textContent = 'Checking this breach…';
      var controller = new AbortController();
      var timer = setTimeout(function () { controller.abort(); }, 65000);
      try {
        var response = await fetch((window.MYRECON && window.MYRECON.apiBase || '') + '/api/breach-check', {
          method: 'POST', credentials: 'omit', cache: 'no-store', signal: controller.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: input.value.trim(), targets: targets })
        });
        if (!response.ok) throw new Error(response.status === 429 ? 'rate_limited' : 'unavailable');
        var data = await response.json();
        if (!['found', 'not_found', 'unsupported', 'rate_limited', 'unavailable'].includes(data.state) || typeof data.message !== 'string') throw new Error('unavailable');
        result.dataset.state = data.state;
        result.textContent = data.message;
      } catch (error) {
        result.dataset.state = 'unavailable';
        result.textContent = error.message === 'rate_limited' ? 'The service is busy. Please try again later.' : 'We could not complete the check. Please try again. No result was established.';
      } finally {
        clearTimeout(timer);
        running = false;
        button.disabled = false;
        input.readOnly = false;
        form.removeAttribute('aria-busy');
      }
    });
  });
})();
