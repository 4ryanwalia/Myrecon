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
          button{padding:12px 16px;border:0;border-radius:8px;background:var(--accent,#4f8cff);color:#fff;font:inherit;font-weight:700;cursor:pointer}
          p{margin:0;color:var(--text-dim,#a9b2c2);font-size:.9rem;line-height:1.5}
          @media(max-width:520px){.row{display:grid}button{width:100%}}
        </style>
        <form aria-label="Search a public username">
          <label for="seo-username">Username</label>
          <div class="row"><input id="seo-username" name="username" type="text" autocomplete="off" autocapitalize="none" spellcheck="false" maxlength="100" placeholder="Enter a username" required>
          <button type="submit">Search public platforms</button></div>
          <p>Use usernames you own or are authorized to review. Results require manual confirmation.</p>
        </form>`;
      root.querySelector("form").addEventListener("submit", (event) => {
        event.preventDefault();
        const value = root.querySelector("input").value.trim().replace(/^@+/, "");
        if (!value) return;
        const params = new URLSearchParams({ tool: "username", q: value });
        window.location.assign(`/#${params.toString()}`);
      });
    }
  }
  if (!customElements.get("username-search-input")) {
    customElements.define("username-search-input", UsernameSearchInput);
  }
})();
