/* Shared by the vanilla JS lookup and investigation views. */
(function () {
  "use strict";
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function notice(data) {
    const errors = Array.isArray(data?.errors) ? data.errors : [];
    if (!errors.length && !data?.partial) return "";
    const messages = [...new Set(errors.filter((e) => e && typeof e === "object")
      .map((e) => e.source === "LeakCheck"
        ? (e.code === "rate_limited" ? "LeakCheck API is rate-limited, displaying other results."
          : "LeakCheck API currently unreachable, displaying other results.")
        : e.message || "A lookup source is unavailable. Displaying completed results."))];
    return `<aside class="partial-notice" role="status"><strong>Search partially completed</strong>
      <p>Completed findings are shown below. Unavailable checks do not mean no match.</p>
      <ul>${(messages.length ? messages : ["Some checks could not complete."]).map((m) => `<li>${esc(m)}</li>`).join("")}</ul></aside>`;
  }
  window.MyReconPartial = { notice };
})();
