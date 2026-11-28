(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", () => {
    // Tool mode hides overview sections. Evidence links must reveal their
    // destination even after a lookup, without changing the current results.
    const reveal = () => {
      if (["#benchmarks", "#changelog"].includes(location.hash)) {
        document.body.classList.remove("tool-mode");
        document.querySelector(location.hash)?.scrollIntoView();
      }
    };
    window.addEventListener("hashchange", reveal);
    document.querySelectorAll('a[href="/#benchmarks"], a[href="/#changelog"]').forEach((link) => {
      link.addEventListener("click", () => document.body.classList.remove("tool-mode"));
    });
    reveal();
  });
})();
