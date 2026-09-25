/* MyRecon, accounts (Google sign-in through Firebase Auth).
 *
 * Exposes window.MyReconAccount. Everything else on the page asks this module
 * for the signed-in state and for the Authorization header to send; nothing
 * else touches Firebase.
 *
 * The Firebase SDK is ~150 KB and most visitors never sign in, so it is not
 * loaded up front. It loads when someone clicks "Sign in", picks the full
 * scan, or has signed in on this browser before (a one-bit hint kept in
 * localStorage). Everyone else pays nothing for accounts existing.
 *
 * Config comes from env.js (generated at build from Vercel env vars, see
 * scripts/gen-env.js). Without it, accounts are off and the page behaves
 * exactly as it did before they existed.
 */
(function () {
  "use strict";

  const FB = window.MYRECON_FIREBASE || null;
  let enabled = !!(FB && FB.apiKey && FB.appId && FB.projectId);
  // Local test account: a dev backend started with DEV_TEST_ACCOUNT=true
  // treats header-less requests as one signed-in test user, so checkout can be
  // tried before Firebase is configured. Only ever looked for on localhost.
  let devMode = false;
  const isLocal = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  const SDK = "https://www.gstatic.com/firebasejs/10.14.1/";
  const HINT = "mr_signed_in";
  const CFG = window.MYRECON || { apiBase: "" };

  let mod = null;        // firebase-auth module
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
  function hinted() {
    try { return localStorage.getItem(HINT) === "1"; } catch { return false; }
  }

  function emit() {
    renderNav();
    listeners.forEach((fn) => { try { fn(state()); } catch {} });
  }

  function state() {
    return { enabled, user: user && { uid: user.uid, email: user.email, name: user.displayName, photo: user.photoURL }, account };
  }

  function load() {
    if (!enabled) { markReady(); return Promise.resolve(); }
    if (loading) return loading;
    loading = (async () => {
      const [appMod, authMod] = await Promise.all([
        import(SDK + "firebase-app.js"),
        import(SDK + "firebase-auth.js"),
      ]);
      mod = authMod;
      auth = authMod.getAuth(appMod.initializeApp({
        apiKey: FB.apiKey, authDomain: FB.authDomain || `${FB.projectId}.firebaseapp.com`,
        projectId: FB.projectId, appId: FB.appId,
      }));
      await new Promise((resolve) => {
        authMod.onAuthStateChanged(auth, async (u) => {
          user = u || null;
          hint(!!user);
          account = null;
          if (user) await refreshAccount();
          resolve();
          markReady();
          emit();
        });
      });
    })().catch((e) => {
      console.warn("[account] sign-in unavailable:", e);
      markReady();
    });
    return loading;
  }

  async function token() {
    if (!enabled || devMode) return null;
    if (!loading && !hinted()) return null;
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
      const res = await fetch(CFG.apiBase + "/api/me", {
        headers: devMode ? {} : { Authorization: "Bearer " + (await user.getIdToken()) },
      });
      const data = await res.json().catch(() => ({}));
      account = res.ok ? data.account : null;
    } catch {
      account = null;
    }
    return account;
  }

  async function signIn() {
    if (devMode) return;
    if (!enabled) throw new Error("Sign-in is not available yet.");
    await load();
    if (!mod) throw new Error("Sign-in could not load. Check your connection.");
    const provider = new mod.GoogleAuthProvider();
    provider.setCustomParameters({ prompt: "select_account" });
    await mod.signInWithPopup(auth, provider);
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
        signIn().catch((err) => {
          if (err && err.code === "auth/popup-closed-by-user") return;
          alert(err.message || "Sign-in failed.");
        });
      };
    }
  }

  window.MyReconAccount = {
    get enabled() { return enabled; },
    ready, load, signIn, signOut, authHeaders, token, refreshAccount, onChange, state,
  };

  async function startDevMode() {
    try {
      const res = await fetch(CFG.apiBase + "/api/plans");
      const info = await res.json();
      if (!info.dev_test_account) return false;
    } catch {
      return false;
    }
    enabled = true;
    devMode = true;
    user = { uid: "dev-test-user", email: "dev@localhost (test account)", displayName: "Dev Test",
      photoURL: null };
    await refreshAccount();
    console.info("[account] local test account active (DEV_TEST_ACCOUNT)");
    return true;
  }

  if (!enabled && isLocal) {
    startDevMode().finally(() => { markReady(); emit(); });
  } else if (enabled) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", renderNav);
    } else {
      renderNav();
    }
    if (hinted()) load(); else markReady();
  } else {
    markReady();
  }
})();
