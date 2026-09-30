/* MyRecon, motion layer.
 *
 * Decorative only. Nothing here touches the tool, results, history or the
 * password path in app.js, and every feature bails out cleanly when an
 * element is missing, so the same file runs on all pages.
 *
 * Kept smooth by:
 *  - IntersectionObserver for reveals and counters, never scroll handlers
 *    doing layout reads.
 * Honours prefers-reduced-motion by doing almost nothing.
 */
(function () {
  "use strict";

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var doc = document.documentElement;

  function el(tag, id) {
    var n = document.createElement(tag);
    if (id) n.id = id;
    n.setAttribute("aria-hidden", "true");
    return n;
  }

  /* ---------- Scroll progress ---------- */
  var progress = el("div", "fx-progress");
  document.body.appendChild(progress);
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      var max = doc.scrollHeight - window.innerHeight;
      progress.style.transform = "scaleX(" + (max > 0 ? Math.min(1, window.scrollY / max) : 0) + ")";
      ticking = false;
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- Scroll reveal ---------- */
  var REVEAL = [
    ".section h2", ".section > .container > .sub", ".prose > .sub",
    ".feature", ".step", ".faq details", ".guide-card", ".phone-mock", ".android-copy",
    ".fx-stat", ".vs-card", ".vs-verdict", ".vs-table-wrap", ".vs-cta", ".vs-article h2"
  ].join(",");
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add("fx-in");
      io.unobserve(e.target);
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }) : null;

  if (io && !reduce) {
    var groups = new Map();
    document.querySelectorAll(REVEAL).forEach(function (n) {
      // The short homepage sections should be readable immediately, including
      // after a direct jump to the footer or a full-page capture.
      if (n.closest('#numbers, #features, #faq')) {
        n.classList.add('fx-in');
        return;
      }
      // Stagger siblings inside the same grid so a row cascades in.
      var p = n.parentElement;
      var i = groups.get(p) || 0;
      groups.set(p, i + 1);
      n.style.setProperty("--fx-delay", Math.min(i, 6) * 70 + "ms");
      n.classList.add("fx-reveal");
      io.observe(n);
    });
  } else {
    document.querySelectorAll(REVEAL).forEach(function (n) { n.classList.add("fx-in"); });
  }

  /* ---------- Bring results into view when a lookup starts ----------
     The tool sits in the hero and results render below it
     on narrow screens, so without this a phone user presses Investigate and
     sees nothing change. Watches the button app.js disables while a lookup
     runs, rather than hooking app.js itself. */
  var runBtn = document.getElementById("runBtn"), resultsEl = document.getElementById("results");
  if (runBtn && resultsEl && "MutationObserver" in window) {
    new MutationObserver(function () {
      if (!runBtn.disabled) return;
      setTimeout(function () {
        var top = resultsEl.getBoundingClientRect().top;
        if (top > window.innerHeight * 0.7 || top < 0) {
          window.scrollTo({ top: window.scrollY + top - 80, behavior: reduce ? "auto" : "smooth" });
        }
      }, 60);
    }).observe(runBtn, { attributes: true, attributeFilter: ["disabled"] });
  }

  /* ---------- Counters (elements with data-count) ---------- */
  function runCounter(n) {
    var target = parseFloat(n.getAttribute("data-count"));
    var suffix = n.getAttribute("data-suffix") || "";
    if (reduce || !isFinite(target)) { n.textContent = target.toLocaleString() + suffix; return; }
    var start = performance.now(), dur = 1600;
    (function step(t) {
      var k = Math.min(1, (t - start) / dur);
      var eased = 1 - Math.pow(1 - k, 4);
      n.textContent = Math.round(target * eased).toLocaleString() + suffix;
      if (k < 1) requestAnimationFrame(step);
    })(start);
  }
  var counters = document.querySelectorAll("[data-count]");
  if (counters.length) {
    if ("IntersectionObserver" in window) {
      var cio = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (!e.isIntersecting) return;
          runCounter(e.target);
          var card = e.target.closest(".fx-stat");
          if (card) card.classList.add("fx-in");
          cio.unobserve(e.target);
        });
      }, { threshold: 0.4 });
      counters.forEach(function (c) { cio.observe(c); });
    } else counters.forEach(runCounter);
  }

  /* ---------- Decrypt effect on short headings (data-scramble) ---------- */
  var GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&@<>/\\";
  function scramble(node) {
    var final = node.textContent;
    if (!final || final.length > 70 || reduce) return;
    node.setAttribute("aria-label", final);
    var frame = 0, total = 26;
    (function tick() {
      var out = "";
      for (var i = 0; i < final.length; i++) {
        var ch = final[i];
        var settle = (i / final.length) * total;
        out += (ch === " " || frame >= settle) ? ch : GLYPHS[(Math.random() * GLYPHS.length) | 0];
      }
      node.textContent = out;
      if (++frame <= total) requestAnimationFrame(tick);
      else node.textContent = final;
    })();
  }
  document.querySelectorAll("[data-scramble]").forEach(scramble);

  /* Platform orbit is an illustration, independent of real scan results. */
  var orbit = document.getElementById("fxOrbit");
  if (orbit) {
    var orbitButton = document.getElementById("orbitPause");
    var orbitNodes = orbit.querySelectorAll(".node");
    var orbitSpokes = orbit.querySelectorAll(".spoke");
    var orbitVisible = true, orbitStopped = false, orbitBusy = [];

    function syncOrbit() {
      orbit.classList.toggle("paused", reduce || orbitStopped || !orbitVisible || document.hidden);
    }
    if (orbitButton) {
      orbitButton.hidden = reduce;
      orbitButton.addEventListener("click", function () {
        orbitStopped = !orbitStopped;
        orbitButton.setAttribute("aria-pressed", String(orbitStopped));
        var label = orbitStopped ? "Resume platform animation" : "Pause platform animation";
        orbitButton.setAttribute("aria-label", label);
        orbitButton.title = label;
        orbitButton.querySelector("path").setAttribute("d", orbitStopped ? "M8 5v14l11-7z" : "M7 5h3v14H7zm7 0h3v14h-3z");
        syncOrbit();
      });
    }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        orbitVisible = entries[0].isIntersecting;
        syncOrbit();
      }).observe(orbit);
    }
    document.addEventListener("visibilitychange", syncOrbit);
    syncOrbit();
    if (!reduce) {
      setInterval(function () {
        if (orbitStopped || !orbitVisible || document.hidden || !orbitNodes.length) return;
        var index = Math.floor(Math.random() * orbitNodes.length);
        if (orbitBusy[index]) return;
        orbitBusy[index] = true;
        orbitNodes[index].classList.add("hit");
        if (orbitSpokes[index]) orbitSpokes[index].classList.add("hit");
        setTimeout(function () {
          orbitNodes[index].classList.remove("hit");
          if (orbitSpokes[index]) orbitSpokes[index].classList.remove("hit");
          orbitBusy[index] = false;
        }, 2400);
      }, 850);
    }
  }

})();
