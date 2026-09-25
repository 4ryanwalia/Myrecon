/* MyRecon, accounts (Google sign-in through Firebase Auth).
 *
 * Exposes window.MyReconAccount. Everything else on the page asks this module
 * for the signed-in state and for the Authorization header to send; nothing
 * else touches Firebase.
 *
 * Where the config comes from, first match wins:
 *   1. window.MYRECON_FIREBASE, written into env.js at build time
 *   2. the API's /api/plans, from FIREBASE_WEB_API_KEY on Render
 * Neither present: accounts are off and the page behaves as it always did.
 * On localhost only, a dev backend with DEV_TEST_ACCOUNT=true stands in a
 * fixed test user so checkout can be tried without Google.
 *
 * Popups: a browser only lets a page open a window in direct response to a
 * click. If the ~150 KB SDK were fetched after the click, the Google window
 * would open after an await and be blocked. So once accounts are known to be
 * on, the SDK is fetched in the background at idle, and signIn() opens the
 * popup synchronously when it is ready. If it is not, or the popup is blocked
 * anyway, it falls back to a full-page redirect.
 */
(function () {
  "use strict";

  const SDK = "https://www.gstatic.com/firebasejs/10.14.1/";
  const HINT = "mr_signed_in";
  const CFG = window.MYRECON || { apiBase: "" };
  const isLocal = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);

  let FB = null;
  let enabled = false;
  let devMode = false;
  let mod = null;        // firebase-auth module, once loaded
  let auth = null;
  let user = null;
  let account = null;    // /api/me payload
  let loading = null;
  const listeners = new Set();

  let markReady;
  const ready = new Promise((r) => { markReady = r; });

  function hint(v) {
    try { v ? localStorage.setItem(HINT, "1") : localStorage.removeItem(HINT); } catch {}
  }

  function emit() {
    renderNav();
    listeners.forEach((fn) => { try { fn(state()); } catch {} });
  }

  function state() {
    return {
      enabled,
      user: user && { uid: user.uid, email: user.email, name: user.displayName, photo: user.photoURL },
      account,
    };
  }

  function validConfig(c) {
    return !!(c && c.apiKey && c.appId && c.projectId);
  }

  // ---- SDK ------------------------------------------------------------
  function load() {
    if (!enabled || devMode) return Promise.resolve();
    if (loading) return loading;
    loading = (async () => {
      const [appMod, authMod] = await Promise.all([
        import(SDK + "firebase-app.js"),
        import(SDK + "firebase-auth.js"),
      ]);
      auth = authMod.getAuth(appMod.initializeApp({
        apiKey: FB.apiKey, authDomain: FB.authDomain || `${FB.projectId}.firebaseapp.com`,
        projectId: FB.projectId, appId: FB.appId,
      }));
      mod = authMod;
      // Completes a redirect sign-in (the popup fallback) if one is pending.
      authMod.getRedirectResult(auth).catch((e) => console.warn("[account] redirect:", e.code || e));
      await new Promise((resolve) => {
        authMod.onAuthStateChanged(auth, async (u) => {
          user = u || null;
          hint(!!user);
          account = null;
          if (user) await refreshAccount();
          resolve();
          emit();
        });
      });
    })().catch((e) => {
      console.warn("[account] sign-in unavailable:", e);
      loading = null;
    });
    return loading;
  }

  async function token() {
    if (!enabled || devMode) return null;
    await load();
    return user ? user.getIdToken() : null;
  }

  async function authHeaders() {
    const t = await token();
    return t ? { Authorization: "Bearer " + t } : {};
  }

  async function refreshAccount() {
    if (!user) { account = null; return null; }
    try {
      const headers = devMode ? {} : { Authorization: "Bearer " + (await user.getIdToken()) };
      const res = await fetch(CFG.apiBase + "/api/me", { headers });
      const data = await res.json().catch(() => ({}));
      account = res.ok ? data.account : null;
    } catch {
      account = null;
    }
    return account;
  }

  function provider() {
    const p = new mod.GoogleAuthProvider();
    p.setCustomParameters({ prompt: "select_account" });
    return p;
  }

  // Must be called straight from a click handler, before any await, so the
  // popup counts as user-initiated. See the header comment.
  function signIn() {
    if (devMode) return Promise.resolve();
    if (!enabled) return Promise.reject(new Error("Sign-in is not available yet."));
    if (mod && auth) {
      return mod.signInWithPopup(auth, provider()).then((cred) => {
        // Set now rather than waiting for onAuthStateChanged, so a scan the
        // caller starts on the next line already carries the token.
        if (cred && cred.user) { user = cred.user; hint(true); }
        return cred;
      }).catch((e) => {
        if (e && (e.code === "auth/popup-blocked"
            || e.code === "auth/operation-not-supported-in-this-environment")) {
          return mod.signInWithRedirect(auth, provider());
        }
        throw e;
      });
    }
    // SDK not ready yet (a click in the first moment after page load). A popup
    // opened after this await would be blocked, so go straight to redirect.
    return load().then(() => {
      if (!mod) throw new Error("Sign-in could not load. Check your connection.");
      return mod.signInWithRedirect(auth, provider());
    });
  }

  async function signOut() {
    if (!mod || !auth) return;
    await mod.signOut(auth);
  }

  function onChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  // ---- nav button -----------------------------------------------------
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function friendly(err) {
    const code = err && err.code;
    if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") return "";
    if (code === "auth/unauthorized-domain") {
      return "Sign-in is not enabled for this address yet. Please try again later.";
    }
    if (code === "auth/network-request-failed") return "Network error. Check your connection and try again.";
    return (err && err.message) || "Sign-in failed. Please try again.";
  }

  function renderNav() {
    if (!enabled) return;
    const host = document.querySelector(".nav-inner");
    if (!host) return;
    let btn = document.getElementById("navAccount");
    if (!btn) {
      btn = document.createElement("a");
      btn.id = "navAccount";
      btn.className = "nav-account";
      const theme = document.getElementById("themeToggle");
      host.insertBefore(btn, theme || null);
    }
    if (user) {
      const tier = account && account.tier === "pro" ? "Pro" : "Free";
      const initial = (user.displayName || user.email || "?").trim().charAt(0).toUpperCase();
      btn.href = "/pricing.html#account";
      btn.removeAttribute("role");
      btn.onclick = null;
      btn.innerHTML = `<span class="nav-avatar" aria-hidden="true">${esc(initial)}</span>`
        + `<span class="nav-tier${tier === "Pro" ? " pro" : ""}">${tier}</span>`;
      btn.setAttribute("aria-label", `Account: ${tier} plan`);
    } else {
      btn.href = "#";
      btn.setAttribute("role", "button");
      btn.textContent = "Sign in";
      btn.setAttribute("aria-label", "Sign in with Google");
      btn.onclick = (e) => {
        e.preventDefault();
        signIn().catch((err) => { const m = friendly(err); if (m) alert(m); });
      };
    }
  }

  window.MyReconAccount = {
    get enabled() { return enabled; },
    ready, load, signIn, signOut, authHeaders, token, refreshAccount, onChange, state,
    friendly,
  };

  // ---- start-up -------------------------------------------------------
  async function planInfo() {
    try {
      const res = await fetch(CFG.apiBase + "/api/plans");
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  }

  function whenIdle(fn) {
    if ("requestIdleCallback" in window) requestIdleCallback(fn, { timeout: 3000 });
    else setTimeout(fn, 1500);
  }

  async function start() {
    if (validConfig(window.MYRECON_FIREBASE)) {
      FB = window.MYRECON_FIREBASE;
    } else {
      const info = await planInfo();
      if (info && validConfig(info.firebase)) {
        FB = info.firebase;
      } else if (info && info.dev_test_account && isLocal) {
        enabled = true;
        devMode = true;
        user = { uid: "dev-test-user", email: "dev@localhost (test account)",
          displayName: "Dev Test", photoURL: null };
        await refreshAccount();
        console.info("[account] local test account active (DEV_TEST_ACCOUNT)");
        return;
      }
    }
    if (!FB) return;
    enabled = true;
    renderNav();
    // A returning signed-in visitor needs the SDK now to know who they are;
    // anyone else gets it at idle so the sign-in popup can open on click.
    let signedInBefore = false;
    try { signedInBefore = localStorage.getItem(HINT) === "1"; } catch {}
    if (signedInBefore) await load();
    else whenIdle(() => load());
  }

  const begin = () => start().finally(() => { markReady(); emit(); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", begin);
  else begin();
})();
