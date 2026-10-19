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
    root.querySelectorAll("img[data-email-photo]").forEach(img => {
      if (wired.has(img)) return;
      wired.add(img);
      const original = img.getAttribute("src") || "";
      let retried = false;
      const loaded = () => {
        if (!img.naturalWidth) return;
        const parent = img.parentElement;
        if (parent) { parent.classList.add("loaded"); parent.removeAttribute("title"); }
      };
      const error = () => {
        const retry = source(original, apiBase);
        if (!retried && retry && retry !== original) {
          retried = true;
          img.setAttribute("crossorigin", "anonymous");
          img.src = retry;
        } else failed(img);
      };
      img.addEventListener("load", loaded);
      img.addEventListener("error", error);
      // Covers cached images that completed before the renderer attached listeners.
      if (img.complete) { if (img.naturalWidth) loaded(); else error(); }
    });
  }

  scope.EmailPhotos = Object.freeze({ source, failed, wire });
})(window);
