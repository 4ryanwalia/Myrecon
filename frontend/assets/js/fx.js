/* MyRecon, motion layer.
 *
 * Decorative only. Nothing here touches the tool, results, history or the
 * password path in app.js, and every feature bails out cleanly when an
 * element is missing, so the same file runs on all pages.
 *
 * Kept smooth by:
 *  - one rAF loop for the particle canvas, capped at ~40 fps and stopped
 *    entirely while the tab is hidden;
 *  - node count scaled to viewport area and capped, devicePixelRatio capped
 *    at 1.5 (the lines are soft anyway, 3x rendering buys nothing);
 *  - one delegated pointermove listener, throttled to a frame, writing CSS
 *    variables instead of styles per card;
 *  - IntersectionObserver for reveals and counters, never scroll handlers
 *    doing layout reads.
 * Honours prefers-reduced-motion by doing almost nothing.
 */
(function () {
  "use strict";

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia && window.matchMedia("(pointer: fine)").matches;
  var doc = document.documentElement;

  function el(tag, id) {
    var n = document.createElement(tag);
    if (id) n.id = id;
    n.setAttribute("aria-hidden", "true");
    return n;
  }
  function css(name) { return getComputedStyle(doc).getPropertyValue(name).trim(); }

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
     The tool sits in the hero and results render below it, under the orbit
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

  /* ---------- Hero console: typed lines, example output only ---------- */
  var consoleEl = document.getElementById("fxConsole");
  if (consoleEl) {
    var SCRIPTS = [
      ["<b>$</b> sweep @yourhandle", "<span class='mu'>checking 123 platforms, each match confidence-scored</span>", "<span class='ok'>3 found</span> <span class='mu'>· 1 unconfirmed · the rest clear</span>"],
      ["<b>$</b> email you@example.com", "<span class='mu'>LeakCheck · XposedOrNot · MX · SPF · DMARC</span>", "<span class='ok'>2 named breaches</span> <span class='mu'>· 2019, 2021</span>"],
      ["<b>$</b> domain example.org", "<span class='mu'>RDAP · DNS-over-HTTPS · DMARC verdict</span>", "<span class='ok'>report ready</span> <span class='mu'>· registrar, age, DNSSEC, spoofability</span>"],
      ["<b>$</b> password ••••••••", "<span class='mu'>SHA-1 in browser · 5-char prefix sent · k-anonymity</span>", "<span class='ok'>seen 0 times</span> <span class='mu'>· never left this device</span>"]
    ];
    var lines = consoleEl.querySelectorAll(".ln");
    var si = 0;
    var plain = function (h) { var d = document.createElement("div"); d.innerHTML = h; return d.textContent; };
    function play() {
      var s = SCRIPTS[si++ % SCRIPTS.length];
      lines.forEach(function (l) { l.innerHTML = "&nbsp;"; l.classList.remove("fx-caret"); });
      if (reduce) { s.forEach(function (h, i) { lines[i].innerHTML = h; }); return; }
      var li = 0;
      (function nextLine() {
        if (li >= s.length) { lines[s.length - 1].classList.add("fx-caret"); setTimeout(play, 2600); return; }
        var target = s[li], text = plain(target), c = 0, line = lines[li];
        line.classList.add("fx-caret");
        (function type() {
          if (c <= text.length) {
            line.textContent = text.slice(0, c) || " ";
            c += li === 0 ? 1 : 3;
            setTimeout(type, li === 0 ? 38 : 14);
          } else {
            line.innerHTML = target;
            line.classList.remove("fx-caret");
            li++;
            setTimeout(nextLine, li === 1 ? 250 : 420);
          }
        })();
      })();
    }
    play();
  }

  if (reduce) return;

  /* ---------- Pointer: card spotlight + cursor glow + phone tilt ---------- */
  var SPOT = ".feature,.step,.guide-card,.vs-card,.fx-card,.results .card";
  var glow = null;
  if (finePointer) {
    glow = el("div", "fx-cursor");
    document.body.appendChild(glow);
  }
  var px = 0, py = 0, pending = false, lastTarget = null;
  var phone = document.querySelector(".phone-mock");
  document.addEventListener("pointermove", function (e) {
    px = e.clientX; py = e.clientY; lastTarget = e.target;
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () {
      pending = false;
      if (glow) {
        glow.classList.add("on");
        glow.style.transform = "translate3d(" + px + "px," + py + "px,0)";
      }
      var card = lastTarget && lastTarget.closest ? lastTarget.closest(SPOT) : null;
      if (card) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--mx", (px - r.left) + "px");
        card.style.setProperty("--my", (py - r.top) + "px");
      }
      if (phone) {
        var pr = phone.getBoundingClientRect();
        if (pr.bottom > 0 && pr.top < window.innerHeight) {
          var dx = (px - (pr.left + pr.width / 2)) / window.innerWidth;
          var dy = (py - (pr.top + pr.height / 2)) / window.innerHeight;
          phone.style.transform = "perspective(900px) rotateY(" + (dx * 10).toFixed(2) + "deg) rotateX(" + (-dy * 8).toFixed(2) + "deg)";
        }
      }
    });
  }, { passive: true });
  document.addEventListener("pointerleave", function () { if (glow) glow.classList.remove("on"); });

  /* ---------- Cursor ring: trails the crosshair, locks onto controls ---------- */
  if (finePointer) {
    var ring = el("div", "fx-ring");
    document.body.appendChild(ring);
    var rx = -100, ry = -100, tx = -100, ty = -100, ringLive = false, chasing = false;
    var LOCK = "a,button,summary,label,select,[role='tab'],[role='button'],.chip,.pivot,.card-link";
    var TEXT = "input:not([type=checkbox]):not([type=radio]),textarea,[contenteditable='true']";
    document.addEventListener("pointermove", function (e) {
      tx = e.clientX; ty = e.clientY;
      if (!ringLive) { rx = tx; ry = ty; ringLive = true; ring.classList.add("on"); }
      if (!chasing) { chasing = true; requestAnimationFrame(follow); }
      var t = e.target && e.target.closest ? e.target : null;
      ring.classList.toggle("lock", !!(t && t.closest(LOCK)));
      ring.classList.toggle("text", !!(t && t.closest(TEXT)));
    }, { passive: true });
    document.addEventListener("pointerdown", function () { ring.classList.add("down"); }, { passive: true });
    document.addEventListener("pointerup", function () { ring.classList.remove("down"); }, { passive: true });
    document.documentElement.addEventListener("pointerleave", function () { ring.classList.remove("on"); ringLive = false; });
    // Eases toward the pointer, then stops until the next pointermove, so a
    // still mouse costs nothing.
    function follow() {
      rx += (tx - rx) * 0.22; ry += (ty - ry) * 0.22;
      var done = Math.abs(tx - rx) < 0.3 && Math.abs(ty - ry) < 0.3;
      if (done) { rx = tx; ry = ty; }
      ring.style.transform = "translate3d(" + rx.toFixed(1) + "px," + ry.toFixed(1) + "px,0)";
      if (done) chasing = false; else requestAnimationFrame(follow);
    }
  }

  /* ---------- Hero orbit: random platforms get "found" ----------
     Illustration only, like the console: it never claims a real result. */
  var orbit = document.getElementById("fxOrbit");
  if (orbit) {
    var nodes0 = orbit.querySelectorAll(".node"), spokes0 = orbit.querySelectorAll(".spoke");
    var hitsEl = document.getElementById("fxHits"), hits = 0, visible = true, busy = [];
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (e) {
        visible = e[0].isIntersecting;
        orbit.classList.toggle("paused", !visible);
      }).observe(orbit);
    }
    setInterval(function () {
      if (!visible || document.hidden) return;
      var i = (Math.random() * nodes0.length) | 0;
      if (busy[i]) return;
      busy[i] = true;
      nodes0[i].classList.add("hit"); spokes0[i].classList.add("hit");
      if (hitsEl) hitsEl.textContent = String(++hits % 124);
      setTimeout(function () {
        nodes0[i].classList.remove("hit"); spokes0[i].classList.remove("hit"); busy[i] = false;
      }, 2400);
    }, 850);
  }

  /* ---------- Radar blips ---------- */
  var radar = document.querySelector(".fx-radar");
  if (radar) {
    for (var b = 0; b < 6; b++) {
      var i = document.createElement("i");
      var ang = Math.random() * Math.PI * 2, rad = 18 + Math.random() * 28;
      i.style.left = (50 + Math.cos(ang) * rad) + "%";
      i.style.top = (50 + Math.sin(ang) * rad) + "%";
      // Delay matches the sweep angle so the blip lights as the beam passes.
      var deg = ((ang * 180 / Math.PI) + 90 + 360) % 360;
      i.style.animationDelay = (deg / 360 * 5.5).toFixed(2) + "s";
      radar.appendChild(i);
    }
  }

  /* ---------- Particle network ---------- */
  var canvas = el("canvas", "fx-net");
  document.body.insertBefore(canvas, document.body.firstChild);
  var ctx = canvas.getContext("2d");
  if (!ctx) return;
  var W = 0, H = 0, DPR = Math.min(window.devicePixelRatio || 1, 1.5);
  var nodes = [], LINK = 130, colA = "", colB = "";

  function palette() { colA = css("--neon") || "#22d3ee"; colB = css("--accent") || "#4a8bf7"; }
  function resize() {
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = W * DPR; canvas.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    var want = Math.max(18, Math.min(70, Math.round(W * H / 22000)));
    while (nodes.length < want) nodes.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35, r: Math.random() * 1.6 + .6 });
    nodes.length = want;
    LINK = W < 720 ? 95 : 130;
  }
  palette(); resize();
  var rt;
  window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(resize, 150); }, { passive: true });
  new MutationObserver(palette).observe(doc, { attributes: true, attributeFilter: ["data-theme"] });

  var last = 0, running = true, mx = -9999, my = -9999;
  document.addEventListener("pointermove", function (e) { mx = e.clientX; my = e.clientY; }, { passive: true });
  document.addEventListener("visibilitychange", function () {
    running = !document.hidden;
    if (running) requestAnimationFrame(draw);
  });

  function hexA(hex, a) {
    if (hex[0] !== "#" || hex.length < 7) return hex;
    var n = parseInt(hex.slice(1, 7), 16);
    return "rgba(" + (n >> 16) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
  }

  function draw(t) {
    if (!running) return;
    requestAnimationFrame(draw);
    if (t - last < 25) return; // ~40 fps is plenty for drifting dots
    last = t;
    ctx.clearRect(0, 0, W, H);
    var n = nodes.length, L2 = LINK * LINK;
    for (var a = 0; a < n; a++) {
      var p = nodes[a];
      p.x += p.vx; p.y += p.vy;
      if (p.x < -20) p.x = W + 20; else if (p.x > W + 20) p.x = -20;
      if (p.y < -20) p.y = H + 20; else if (p.y > H + 20) p.y = -20;
      // Gentle pull toward the pointer so the web "notices" you.
      var dxm = mx - p.x, dym = my - p.y, dm = dxm * dxm + dym * dym;
      if (dm < 32000) { p.x += dxm * 0.004; p.y += dym * 0.004; }
    }
    ctx.lineWidth = 1;
    for (a = 0; a < n; a++) {
      var A = nodes[a];
      for (var b = a + 1; b < n; b++) {
        var B = nodes[b], dx = A.x - B.x, dy = A.y - B.y, d = dx * dx + dy * dy;
        if (d < L2) {
          ctx.strokeStyle = hexA(colB, (1 - d / L2) * 0.35);
          ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
        }
      }
      var dA = (mx - A.x) * (mx - A.x) + (my - A.y) * (my - A.y);
      if (dA < L2 * 1.6) {
        ctx.strokeStyle = hexA(colA, (1 - dA / (L2 * 1.6)) * 0.6);
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(mx, my); ctx.stroke();
      }
    }
    ctx.fillStyle = colA;
    for (a = 0; a < n; a++) {
      ctx.beginPath(); ctx.arc(nodes[a].x, nodes[a].y, nodes[a].r, 0, 6.2832); ctx.fill();
    }
  }
  requestAnimationFrame(draw);
})();
