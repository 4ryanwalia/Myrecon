/* Shared static-site equivalent of the kit's UsernameSearchInput component. */
(function () {
  class UsernameSearchInput extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `
        <style>
          :host{display:block;color:inherit;font:inherit}
          form{display:grid;gap:10px;margin-top:16px}
          label{font-weight:700}
          .row{display:flex;gap:10px;flex-wrap:wrap}
          input{flex:1 1 220px;min-width:0;padding:12px 14px;border:1px solid var(--border,#667085);border-radius:8px;background:var(--surface-2,#0b111b);color:inherit;font:inherit}
          button{padding:12px 16px;border:0;border-radius:8px;background:var(--accent-2,#252525);color:var(--on-accent,#fff);font:inherit;font-weight:700;cursor:pointer}
          p{margin:0;color:var(--text-dim,#a9b2c2);font-size:.9rem;line-height:1.5}
          @media(max-width:520px){.row{display:grid}button{width:100%}}
        </style>
        <form aria-label="Search a public username">
          <label for="seo-username">Username</label>
          <div class="row"><input id="seo-username" name="username" type="text" autocomplete="off" autocapitalize="none" spellcheck="false" maxlength="8192" placeholder="Enter a username or paste a profile link." required>
          <button type="submit">Search public platforms</button></div>
          <p>Use usernames you own or are authorized to review. Results require manual confirmation.</p>
        </form>`;
      root.querySelector("form").addEventListener("submit", (event) => {
        event.preventDefault();
        const value = root.querySelector("input").value.trim().replace(/^@/, "");
        if (!value) return;
        const params = new URLSearchParams({ tool: "username", q: value });
        window.location.assign(`/#${params.toString()}`);
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

