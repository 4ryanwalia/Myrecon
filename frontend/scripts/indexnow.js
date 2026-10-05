/* IndexNow, tell the search engines the moment something publishes.
 *
 * Crawling is a queue. A new breach article normally waits days for a bot to
 * come round. IndexNow notifies participating engines of changes; it does
 * not guarantee crawling, indexing, ranking, or a completion time.
 *
 * The endpoint notifies Bing and other search engines that participate in
 * IndexNow. Bing says its search index powers services including DuckDuckGo,
 * but this is not a direct DuckDuckGo submission. Google does not participate,
 * so this complements Search Console rather than replacing it.
 *
 * Ownership is proved by hosting a file named after the key, containing the
 * key, at the site root. That is why the key is public and why it being public
 * is fine: possession of it proves nothing, serving it from the domain does.
 *
 * Only URLs that actually changed are submitted. The protocol asks for this
 * explicitly, and re-submitting an unchanged page on every run is how a domain
 * gets its submissions throttled or ignored.
 *
 *   node scripts/indexnow.js <url> [<url> ...]
 *
 * Run after deployment. Failure is reported to the notification workflow;
 * the production deployment and sitemap remain available independently.
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("node:child_process");

const HOST = "www.myrecon.xyz";
const ENDPOINT = "https://api.indexnow.org/indexnow";

/** Must match the filename of the key file served from the site root. */
const KEY = "ed34c84a1c19af372b78c1a66d636aaa";

const KEY_FILE = path.join(__dirname, "..", `${KEY}.txt`);
const ROOT = path.resolve(__dirname, "../..");

function publicUrl(file, html) {
  if (!file.startsWith("frontend/") || !file.endsWith(".html") ||
      /\/(?:content|scripts|data|tests)\//.test(file) || file === "frontend/404.html") return null;
  if (!/<title\b/i.test(html)) return null;
  const tags = html.match(/<meta\b[^>]*>/gi) || [];
  if (tags.some(tag => /\bname\s*=\s*["'](?:robots|googlebot|bingbot)["']/i.test(tag) &&
    /\bcontent\s*=\s*["'][^"']*\b(?:noindex|none)\b/i.test(tag))) return null;
  const canonical = (html.match(/<link\b[^>]*>/gi) || [])
    .find(tag => /\brel\s*=\s*["']canonical["']/i.test(tag));
  const href = canonical?.match(/\bhref\s*=\s*["']([^"']+)["']/i)?.[1];
  const fallback = file.slice("frontend/".length).replace(/index\.html$/, "");
  try {
    const url = new URL(href || `/${fallback}`, `https://${HOST}`);
    if (url.protocol !== "https:" || url.host !== HOST || url.username || url.password ||
        /^\/(?:api|content)\//.test(url.pathname)) return null;
    url.search = "";
    url.hash = "";
    return url.href;
  } catch { return null; }
}

function changedUrls(before, after) {
  const git = args => execFileSync("git", args, { cwd: ROOT, encoding: "utf8", maxBuffer: 20 * 1024 * 1024 });
  const files = git(["diff", "--name-only", "--no-renames", before, after, "--", "frontend"])
    .trim().split(/\r?\n/).filter(file => file.endsWith(".html"));
  const urls = new Set();
  for (const file of files) {
    // Include the old canonical too when a page is deleted or its URL moves.
    for (const ref of [before, after]) {
      let html;
      try { html = git(["show", `${ref}:${file}`]); } catch { continue; }
      const url = publicUrl(file, html);
      if (url) urls.add(url);
    }
  }
  return [...urls];
}

async function main() {
  const args = process.argv.slice(2);
  const candidates = args[0] === "--changed" ? changedUrls(args[1], args[2]) : args;
  const urls = [...new Set(candidates)].filter(value => {
    try { const u = new URL(value); return u.protocol === "https:" && u.host === HOST &&
      !u.username && !u.password && !/^\/(?:api|content)\//.test(u.pathname); }
    catch { return false; }
  });

  if (!fs.existsSync(KEY_FILE)) {
    console.error(`[indexnow] key file missing: ${KEY_FILE}`);
    process.exitCode = 1;
    return;
  }
  if (!urls.length) {
    console.log("[indexnow] nothing changed, nothing to submit");
    return;
  }

  // The protocol caps a batch at 10,000. Nowhere near it, but a run that
  // somehow tried to submit everything should be capped rather than rejected.
  if (urls.length > 10000) throw new Error("Split submissions into batches of at most 10,000 URLs");
  const batch = urls;

  const body = {
    host: HOST,
    key: KEY,
    keyLocation: `https://${HOST}/${KEY}.txt`,
    urlList: batch,
  };

  try {
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });

    // 200 accepted, 202 accepted but key still being validated. Both fine.
    if (res.status === 200 || res.status === 202) {
      console.log(`[indexnow] submitted ${batch.length} URL(s), HTTP ${res.status}`);
    } else {
      // 403 means the key file did not verify, 422 means a URL did not belong
      // to the host. Both are worth seeing in the log rather than swallowing.
      console.warn(`[indexnow] HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
      process.exitCode = 1;
    }
  } catch (err) {
    console.warn(`[indexnow] submission failed: ${err.message}`);
    process.exitCode = 1;
  }
}

module.exports = { publicUrl, changedUrls };
if (require.main === module) main().catch(err => {
  console.error(`[indexnow] ${err.message}`);
  process.exitCode = 1;
});
