/**
 * The MyRecon breach widget, a live breach list for somebody else's site.
 *
 *   <div id="myrecon-breaches"></div>
 *   <script src="https://www.myrecon.xyz/assets/js/embed.js"
 *           data-count="5" data-theme="auto" async></script>
 *
 * Three decisions in here are load-bearing:
 *
 *  1. **The credit is rendered, not requested.** The data is Have I Been
 *     Pwned's under CC BY 4.0, and attribution is a condition of that licence
 *     rather than a courtesy. A widget that left crediting to the person
 *     installing it would put every one of them in breach by default. So the
 *     footer is drawn by the same function that draws the rows, and removing
 *     it means editing this file, at which point it is a deliberate act, not
 *     an oversight.
 *
 *  2. **Shadow DOM, so the host page's CSS cannot reach in.** An embed that
 *     inherits its host's stylesheet looks broken on most sites and there is
 *     no way to test against all of them. A closed style boundary is the only
 *     version that renders the same everywhere.
 *
 *  3. **Nothing is tracked.** No cookie, no identifier, no beacon, no record
 *     of which site loaded it. It is one GET for a static JSON file. A
 *     privacy tool distributing a tracking pixel would be an odd thing.
 *
 * Fails silent: if the fetch fails, the container is left exactly as it was.
 * A visitor to somebody else's site should never see our error message.
 */
(function () {
  "use strict";

  var CONTAINER_ID = "myrecon-breaches";
  var MAX = 10;

  // document.currentScript is null once an async script has run, so it is read
  // immediately at parse time rather than inside the fetch callback.
  var script = document.currentScript;

  /**
   * Where to fetch from, taken from this script's own URL.
   *
   * Hardcoding the production origin would mean the widget could never be
   * tested anywhere it is not already deployed, including locally, which is
   * the one place a bug in it can be caught before it is on other people's
   * sites. Reading it back from `src` makes staging and localhost work with
   * no edit, and on the real site it resolves to exactly the same origin it
   * was hardcoded to.
   */
  var ORIGIN = (function () {
    try {
      if (script && script.src) return new URL(script.src).origin;
    } catch (e) { /* fall through */ }
    return "https://www.myrecon.xyz";
  })();

  var ENDPOINT = ORIGIN + "/data/v1/latest.json";

  /** The credit always points at the canonical site, never at a staging copy. */
  var CANONICAL = "https://www.myrecon.xyz";

  function attr(name, fallback) {
    if (!script) return fallback;
    var v = script.getAttribute("data-" + name);
    return v === null || v === "" ? fallback : v;
  }

  var count = Math.max(1, Math.min(MAX, parseInt(attr("count", "5"), 10) || 5));
  var theme = attr("theme", "auto");
  var title = attr("title", "Latest data breaches");

  /**
   * Colours for the three themes.
   *
   * "auto" follows the visitor's OS preference through a media query rather
   * than trying to sniff the host page's theme, which is not reliably
   * inspectable from inside a shadow root.
   */
  var PALETTES = {
    dark: { bg: "#0b0f14", fg: "#e7edf3", dim: "#9aa7b4", mute: "#6b7a89", line: "#1e2936", accent: "#4c8dff" },
    light: { bg: "#ffffff", fg: "#10161d", dim: "#4a5866", mute: "#6b7a89", line: "#e3e8ee", accent: "#1b5fd9" },
  };

  function severityColour(band) {
    if (band === "Severe") return "#ef6461";
    if (band === "Serious") return "#e0a84b";
    return "#4cc38a";
  }

  function fmtAccounts(n) {
    if (typeof n !== "number" || !isFinite(n)) return "";
    if (n >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, "") + "B accounts";
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M accounts";
    if (n >= 1e3) return Math.round(n / 1e3) + "K accounts";
    return n + " accounts";
  }

  function fmtDate(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function css(p) {
    return (
      ":host{all:initial}" +
      "*{box-sizing:border-box;margin:0;padding:0}" +
      ".w{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;" +
      "background:" + p.bg + ";color:" + p.fg + ";border:1px solid " + p.line + ";" +
      "border-radius:12px;overflow:hidden;max-width:100%}" +
      ".h{padding:14px 16px;border-bottom:1px solid " + p.line + ";font-size:14px;font-weight:600;" +
      "display:flex;align-items:center;gap:8px}" +
      ".h span{width:7px;height:7px;border-radius:2px;background:" + p.accent + ";flex:none}" +
      "ul{list-style:none}" +
      "li{border-bottom:1px solid " + p.line + "}" +
      "li:last-child{border-bottom:0}" +
      "a.r{display:block;padding:12px 16px;text-decoration:none;color:inherit}" +
      "a.r:hover{background:" + p.line + "}" +
      "a.r:focus-visible{outline:2px solid " + p.accent + ";outline-offset:-2px}" +
      ".t{font-size:14px;font-weight:600;display:flex;align-items:center;gap:7px}" +
      ".d{width:6px;height:6px;border-radius:50%;flex:none}" +
      ".m{font-size:12px;color:" + p.dim + ";margin-top:3px}" +
      ".f{padding:10px 16px;border-top:1px solid " + p.line + ";font-size:11px;color:" + p.mute + ";line-height:1.5}" +
      ".f a{color:" + p.mute + ";text-decoration:underline}" +
      ".f a:hover{color:" + p.fg + "}"
    );
  }

  function render(host, data) {
    var breaches = (data && data.breaches ? data.breaches : []).slice(0, count);
    if (!breaches.length) return;

    var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
    var palette = theme === "light" ? PALETTES.light : PALETTES.dark;

    var style = document.createElement("style");
    style.textContent = css(palette);
    if (theme === "auto") {
      // Dark is the default above; this only overrides for a light OS setting.
      style.textContent +=
        "@media(prefers-color-scheme:light){" +
        ".w{background:" + PALETTES.light.bg + ";color:" + PALETTES.light.fg +
        ";border-color:" + PALETTES.light.line + "}" +
        "li,.h,.f{border-color:" + PALETTES.light.line + "}" +
        ".m{color:" + PALETTES.light.dim + "}" +
        "a.r:hover{background:" + PALETTES.light.line + "}}";
    }
    root.appendChild(style);

    var wrap = document.createElement("div");
    wrap.className = "w";

    var head = document.createElement("div");
    head.className = "h";
    var dot = document.createElement("span");
    head.appendChild(dot);
    // textContent throughout, never innerHTML, the payload is ours, but a
    // widget that interpolates remote strings into HTML is one upstream
    // change away from being an XSS vector on every site that embeds it.
    head.appendChild(document.createTextNode(title));
    wrap.appendChild(head);

    var ul = document.createElement("ul");
    breaches.forEach(function (b) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.className = "r";
      a.href = b.url || CANONICAL + "/breaches/";
      a.target = "_blank";
      a.rel = "noopener";

      var t = document.createElement("div");
      t.className = "t";
      var sev = document.createElement("i");
      sev.className = "d";
      sev.style.background = severityColour(b.band);
      t.appendChild(sev);
      t.appendChild(document.createTextNode(b.title || b.name || b.slug));
      a.appendChild(t);

      var meta = [fmtDate(b.breach_date), fmtAccounts(b.accounts)].filter(Boolean).join(" · ");
      if (meta) {
        var m = document.createElement("div");
        m.className = "m";
        m.textContent = meta;
        a.appendChild(m);
      }

      li.appendChild(a);
      ul.appendChild(li);
    });
    wrap.appendChild(ul);

    // The attribution. Both credits are required for different reasons: HIBP
    // by the CC BY licence on the data, MyRecon because this is our widget.
    var foot = document.createElement("div");
    foot.className = "f";
    foot.appendChild(document.createTextNode("Data from "));
    var hibp = document.createElement("a");
    hibp.href = "https://haveibeenpwned.com/";
    hibp.target = "_blank";
    hibp.rel = "noopener";
    hibp.textContent = "Have I Been Pwned";
    foot.appendChild(hibp);
    foot.appendChild(document.createTextNode(" (CC BY 4.0), via "));
    var mr = document.createElement("a");
    mr.href = CANONICAL + "/breaches/";
    mr.target = "_blank";
    mr.rel = "noopener";
    mr.textContent = "MyRecon";
    foot.appendChild(mr);
    wrap.appendChild(foot);

    root.appendChild(wrap);
  }

  function start() {
    var host = document.getElementById(CONTAINER_ID);
    if (!host) return;
    fetch(ENDPOINT, { mode: "cors", credentials: "omit" })
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function (data) {
        render(host, data);
      })
      .catch(function () {
        /* Silent. See the header comment. */
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
