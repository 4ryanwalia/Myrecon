/* MyRecon — runtime configuration.
 *
 * The backend base URL is never hardcoded in application logic. It resolves as:
 *   1. window.MYRECON_API_BASE           (explicit override, e.g. self-hosting)
 *   2. localhost during local development
 *   3. "" (same-origin) in production — Vercel rewrites /api/* to the Render API
 *      (see frontend/vercel.json), so there are no cross-origin URLs to leak.
 */
(function () {
  const host = location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  const base =
    (typeof window !== "undefined" && window.MYRECON_API_BASE) ||
    (isLocal ? "http://localhost:5000" : "");

  window.MYRECON = {
    apiBase: base,
    endpoints: {
      username: "/api/username",
      fullname: "/api/fullname",
      email: "/api/email",
      domain: "/api/domain",
      dns: "/api/dns",
      whois: "/api/whois",
      ip: "/api/ip",
      image: "/api/image",
      health: "/api/health",
    },
  };
})();
