/* Public email profile photos: direct delivery, one bounded CDN retry, fallback. */
(function (scope) {
  "use strict";
  const hosts = new Set([
    "avatars.githubusercontent.com", "avatars0.githubusercontent.com", "avatars1.githubusercontent.com",
    "avatars2.githubusercontent.com", "avatars3.githubusercontent.com", "lh3.googleusercontent.com",
    "lh4.googleusercontent.com", "lh5.googleusercontent.com", "lh6.googleusercontent.com",
    "yt3.googleusercontent.com", "media.licdn.com", "media-exp1.licdn.com", "media-exp2.licdn.com",
    "media-exp3.licdn.com", "www.gravatar.com", "secure.gravatar.com", "gravatar.com",
    "0.gravatar.com", "1.gravatar.com", "2.gravatar.com"
  ]);
  const wired = new WeakSet();
  const retries = new Set();
  const MAX_BYTES = 2 * 1024 * 1024;
  const account = () => scope.MyReconAccount;
  const uid = () => account()?.state?.().user?.uid || null;

  function revoke(entry) {
    if (entry?.objectUrl) {
      URL.revokeObjectURL(entry.objectUrl);
      entry.objectUrl = null;
    }
  }
  function discard(entry, remove = false) {
    entry.controller?.abort();
    revoke(entry);
    retries.delete(entry);
    if (remove && entry.img.isConnected) failed(entry.img);
  }
  async function imageBlob(response) {
    const type = (response.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
    if (!response.ok || !["image/png", "image/jpeg", "image/gif", "image/webp"].includes(type)) throw new Error("Photo unavailable");
    const declared = response.headers.get("Content-Length");
    if (declared !== null && (!Number.isFinite(Number(declared)) || Number(declared) < 0 || Number(declared) > MAX_BYTES)) throw new Error("Photo too large");
    if (!response.body?.getReader) {
      const blob = await response.blob();
      if (!blob.size || blob.size > MAX_BYTES) throw new Error("Photo too large");
      return blob;
    }
    const reader = response.body.getReader(), chunks = [];
    let size = 0;
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_BYTES) throw new Error("Photo too large");
        chunks.push(value);
      }
      if (!size) throw new Error("Photo unavailable");
      return new Blob(chunks, { type });
    } finally { await reader.cancel().catch(() => {}); }
  }

  function source(url, apiBase) {
    try {
      const parsed = new URL(url, scope.location.href);
      if (parsed.protocol !== "https:" || !hosts.has(parsed.hostname) || parsed.username ||
          parsed.password || (parsed.port && parsed.port !== "443") || parsed.hash ||
          parsed.href.length > 4096) return url;
      const base = new URL(apiBase || scope.location.origin, scope.location.href);
      if (!["http:", "https:"].includes(base.protocol)) return url;
      return base.href.replace(/\/$/, "") + "/api/email/photo?url=" + encodeURIComponent(parsed.href);
    } catch { return url; }
  }

  function failed(img) {
    const parent = img.parentElement;
    if (parent) {
      parent.classList.remove("loaded");
      parent.title = "Photo unavailable";
    }
    img.remove();
  }

  function wire(root, apiBase) {
    for (const entry of retries) if (!entry.img.isConnected) discard(entry);
    root.querySelectorAll("img[data-email-photo]").forEach(img => {
      if (wired.has(img)) return;
      wired.add(img);
      const original = img.getAttribute("src") || "";
      let retried = false;
      let entry = null;
      const loaded = () => {
        if (!img.naturalWidth) return;
        if (entry && uid() !== entry.uid) { discard(entry, true); return; }
        revoke(entry);
        const parent = img.parentElement;
        if (parent) { parent.classList.add("loaded"); parent.removeAttribute("title"); }
      };
      const error = async () => {
        const retry = source(original, apiBase);
        const requestUid = uid();
        if (!retried && retry && retry !== original && requestUid && account()) {
          retried = true;
          entry = { img, uid: requestUid, controller: new AbortController(), objectUrl: null };
          retries.add(entry);
          const timer = setTimeout(() => entry.controller?.abort(), 12000);
          try {
            const headers = await account().authHeaders();
            if (uid() !== requestUid || !img.isConnected) { discard(entry, true); return; }
            const response = await fetch(retry, { headers, signal: entry.controller.signal,
              cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", redirect: "error" });
            const blob = await imageBlob(response);
            if (uid() !== requestUid || !img.isConnected) { discard(entry, true); return; }
            entry.objectUrl = URL.createObjectURL(blob);
            img.removeAttribute("crossorigin");
            img.src = entry.objectUrl;
          } catch {
            discard(entry, true);
          } finally {
            clearTimeout(timer);
            entry.controller = null;
          }
        } else {
          if (entry) discard(entry);
          failed(img);
        }
      };
      img.addEventListener("load", loaded);
      img.addEventListener("error", error);
      // Covers cached images that completed before the renderer attached listeners.
      if (img.complete) { if (img.naturalWidth) loaded(); else error(); }
    });
  }

  account()?.onChange?.((state) => {
    const currentUid = state.user?.uid || null;
    for (const entry of retries) {
      if (!entry.img.isConnected) discard(entry);
      else if (entry.uid !== currentUid) discard(entry, true);
    }
  });

  scope.EmailPhotos = Object.freeze({ source, failed, wire });
})(window);
