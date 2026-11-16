/* The visitor's own country, so the pricing page can offer one checkout:
 * Razorpay inside India, PayPal elsewhere.
 *
 * Vercel sets x-vercel-ip-country on every request (a client cannot supply
 * its own). Nothing is stored or logged; the answer goes back only to the
 * visitor who asked, and it never decides a price: the backend does that.
 * Off Vercel (local preview, tests) this route does not exist and the page
 * falls back to the browser's time zone.
 */
module.exports = (req, res) => {
  const raw = String(req.headers["x-vercel-ip-country"] || "").trim().toUpperCase();
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "private, no-store");
  res.setHeader("X-Robots-Tag", "noindex");
  res.statusCode = 200;
  res.end(JSON.stringify({ country: /^[A-Z]{2}$/.test(raw) ? raw : null }));
};
