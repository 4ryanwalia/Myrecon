/* Remember a content-page promo dismissal for this browser session. */
(function () {
  var key = "myrecon-content-app-promo-dismissed";
  var promos = document.querySelectorAll("[data-content-app-promo]");
  if (!promos.length) return;

  try {
    if (sessionStorage.getItem(key) === "1") {
      promos.forEach(function (promo) { promo.hidden = true; });
      return;
    }
  } catch (_) {
    // Storage can be unavailable in private browsing; dismissal still works.
  }

  promos.forEach(function (promo) {
    var button = promo.querySelector("[data-app-promo-dismiss]");
    if (!button) return;
    button.addEventListener("click", function () {
      promos.forEach(function (item) { item.hidden = true; });
      try { sessionStorage.setItem(key, "1"); } catch (_) { /* optional */ }
    });
  });
})();
