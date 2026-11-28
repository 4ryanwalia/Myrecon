/* Shared static-site equivalent of the kit's UsernameSearchInput component.
   tool="email" switches it to an email lookup; sample="handle" adds a
   one-click example. Either way the search opens on the homepage tool,
   which runs it at once and then removes the query from the address. */
(function () {
  const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  class UsernameSearchInput extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const email = this.getAttribute("tool") === "email";
      const sample = !email && /^[A-Za-z0-9._-]{2,40}$/.test(this.getAttribute("sample") || "") ? this.getAttribute("sample") : "";
      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `
        <style>
          :host{display:block;color:inherit;font:inherit}
          form{display:grid;gap:10px;margin-top:16px}
          label{font-weight:700}
          .row{display:flex;gap:10px;flex-wrap:wrap}
          input[type=text],input[type=email]{flex:1 1 220px;min-width:0;padding:12px 14px;border:1px solid var(--border,#667085);border-radius:8px;background:var(--surface-2,#0b111b);color:inherit;font:inherit}
          button{padding:12px 16px;border:0;border-radius:8px;background:var(--accent-2,#252525);color:var(--on-accent,#fff);font:inherit;font-weight:700;cursor:pointer}
          button.sample{justify-self:start;padding:6px 10px;border:1px solid var(--border,#667085);background:none;color:inherit;font-weight:500;font-size:.9rem}
          .opt{display:flex;gap:8px;align-items:flex-start;font-weight:400;font-size:.92rem;line-height:1.45}
          .opt input{margin-top:3px}
          p{margin:0;color:var(--text-dim,#a9b2c2);font-size:.9rem;line-height:1.5}
          @media(max-width:520px){.row{display:grid}button{width:100%}button.sample{width:auto}}
        </style>
        ${email ? `
        <form aria-label="Look up an email address">
          <label for="seo-email">Email address</label>
          <div class="row"><input id="seo-email" name="email" type="email" autocomplete="off" spellcheck="false" maxlength="320" placeholder="name@example.com" required>
          <button type="submit">Look up this email</button></div>
          <label class="opt"><input type="checkbox" name="linked"> <span>Also check linked accounts on 100+ services with Holehe. This sends the address to each service it checks.</span></label>
          <p>Free, no sign-in. Check addresses you own or are authorized to review.</p>
        </form>` : `
        <form aria-label="Search a public username">
          <label for="seo-username">Username</label>
          <div class="row"><input id="seo-username" name="username" type="text" autocomplete="off" autocapitalize="none" spellcheck="false" maxlength="8192" placeholder="Enter a username or paste a profile link." required>
          <button type="submit">Search public platforms</button></div>
          ${sample ? `<button class="sample" type="button" data-sample="${esc(sample)}">Try an example: ${esc(sample)}</button>` : ""}
          <p>Use usernames you own or are authorized to review. Results require manual confirmation.</p>
        </form>`}`;
      const form = root.querySelector("form");
      const go = (value) => {
        const params = new URLSearchParams({ tool: email ? "email" : "username", q: value });
        if (email && form.querySelector('input[name="linked"]')?.checked) params.set("linked", "1");
        window.location.assign(`/#${params.toString()}`);
      };
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const input = form.querySelector(email ? 'input[name="email"]' : 'input[name="username"]');
        const raw = input.value.trim();
        const value = email ? raw : raw.replace(/^@/, "");
        if (!value) return;
        window.MyReconAnalytics?.toolCtaSubmit?.(email ? "email" : "username", "landing_form");
        go(value);
      });
      root.querySelector("button.sample")?.addEventListener("click", (event) => {
        const value = event.currentTarget.dataset.sample;
        form.querySelector('input[name="username"]').value = value;
        go(value);
      });
    }
  }
  if (typeof customElements !== "undefined" && !customElements.get("username-search-input")) {
    customElements.define("username-search-input", UsernameSearchInput);
  }

  function storageGet(key) {
    try { return window.localStorage.getItem(key); } catch { return null; }
  }
  function storageSet(key, value) {
    try { window.localStorage.setItem(key, value); return true; } catch { return false; }
  }
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = t === "light" ? "#f7f7f4" : "#111111";
    const btn = document.getElementById("themeToggle");
    if (btn) btn.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
  }
  function initShell() {
    if (typeof document === "undefined") return;
    const stored = storageGet("myrecon-theme");
    const saved = stored === "light" || stored === "dark" ? stored : null;
    const defaultTheme = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    applyTheme(saved || defaultTheme);

    const themeBtn = document.getElementById("themeToggle");
    if (themeBtn && !themeBtn.dataset.themeBound) {
      themeBtn.dataset.themeBound = "1";
      themeBtn.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        storageSet("myrecon-theme", next);
        applyTheme(next);
      });
    }

    const navBtn = document.getElementById("navToggle");
    const navLinks = document.getElementById("navLinks");
    if (navBtn && navLinks && !navBtn.dataset.navBound) {
      navBtn.dataset.navBound = "1";
      navBtn.setAttribute("aria-expanded", "false");
      navBtn.setAttribute("aria-controls", "navLinks");
      navBtn.addEventListener("click", () => {
        const open = navLinks.classList.toggle("open");
        navBtn.setAttribute("aria-expanded", String(open));
      });
    }
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initShell, { once: true });
    } else {
      initShell();
    }
  }
})();

