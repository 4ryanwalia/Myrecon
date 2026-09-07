/* IndexNow — tell the search engines the moment something publishes.
 *
 * Crawling is a queue. A new breach article normally waits days for a bot to
 * come round, which for a page whose whole value is being early is most of the
 * value gone. IndexNow inverts it: one HTTP POST and the URL is queued for
 * indexing in minutes.
 *
 * Bing, DuckDuckGo, Yandex and Seznam all consume the same endpoint, so a
 * single submission reaches all of them. Google does NOT participate — it has
 * declined to adopt IndexNow — so this complements Search Console rather than
 * replacing it.
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
 * Exits 0 even on failure. A search-engine ping is not worth failing a deploy
 * over, and the sitemap still covers everything on the slower path.
 */

const fs = require("fs");
const path = require("path");

const HOST = "www.myrecon.xyz";
const ENDPOINT = "https://api.indexnow.org/indexnow";

/** Must match the filename of the key file served from the site root. */
const KEY = "ed34c84a1c19af372b78c1a66d636aaa";

const KEY_FILE = path.join(__dirname, "..", `${KEY}.txt`);

async function main() {
  const urls = process.argv.slice(2).filter((u) => u.startsWith("https://"));

  if (!fs.existsSync(KEY_FILE)) {
    console.error(`[indexnow] key file missing: ${KEY_FILE}`);
    return;
  }
  if (!urls.length) {
    console.log("[indexnow] nothing changed, nothing to submit");
    return;
  }

  // The protocol caps a batch at 10,000. Nowhere near it, but a run that
  // somehow tried to submit everything should be capped rather than rejected.
  const batch = urls.slice(0, 10000);

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
    });

    // 200 accepted, 202 accepted but key still being validated. Both fine.
    if (res.status === 200 || res.status === 202) {
      console.log(`[indexnow] submitted ${batch.length} URL(s) — HTTP ${res.status}`);
    } else {
      // 403 means the key file did not verify, 422 means a URL did not belong
      // to the host. Both are worth seeing in the log rather than swallowing.
      console.warn(`[indexnow] HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
    }
  } catch (err) {
    console.warn(`[indexnow] submission failed: ${err.message}`);
  }
}

main();
