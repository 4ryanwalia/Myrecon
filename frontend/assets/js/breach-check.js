/* The email check on a breach article.
 *
 * Hands the address to the tool on the home page through the deep link it
 * already supports (#tool=email&q=...), which switches to the email tool and
 * runs it. Nothing is submitted from this page and nothing is stored here —
 * the form exists so that someone who arrived searching "was my email in the
 * X breach" can get the answer without first working out where the tool is.
 *
 * Progressive enhancement: with JavaScript off the form simply does nothing
 * and the article still reads, which is why the markup is a real <form> with
 * a real input rather than a button that only exists in script.
 */
(function () {
  "use strict";

  document.querySelectorAll("[data-breach-check]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var input = form.querySelector('input[type="email"]');
      var value = (input && input.value || "").trim();
      if (!value) return;
      // The tool validates properly; this only avoids a pointless round trip.
      if (value.indexOf("@") < 1) {
        input.focus();
        return;
      }
      window.location.href = "/#tool=email&q=" + encodeURIComponent(value);
    });
  });
})();
