/**
 * Publishes the breach archive as a public JSON API.
 *
 * The site already holds two maintained datasets, the breach feed rebuilt
 * from Have I Been Pwned, and 59 original case files, and both sit behind
 * HTML that only a person can read. This emits them as versioned JSON so a
 * developer can put breach data on their own site without scraping ours.
 *
 * That is deliberate distribution, not generosity. A tool that has to be
 * scraped gets scraped badly, loses attribution, and earns nothing; a tool
 * that publishes a clean feed with an attribution requirement earns a link
 * from every site that uses it. The link is the point.
 *
 * ── Licensing, which is the part that must not be got wrong ──────────────
 *
 * HIBP's breach data is CC BY 4.0. That permits redistribution, which is
 * why this file may exist at all, but attribution is a *condition*, not a
 * courtesy, and it is owed to **Have I Been Pwned**, not to us. We are the
 * distributor, not the source.
 *
 * So every payload carries its own `licence` and `attribution` block. A
 * developer who never reads the documentation page and only ever looks at
 * the JSON still cannot miss what they owe. Stripping those fields to make
 * the payload smaller would put every downstream consumer in breach of the
 * licence we redistribute under. Do not do it.
 *
 * The case files are different: they are MyRecon's own writing, so the index
 * is published with a link-back requirement and the article text is not
 * republished here at all.
 *
 * Run from frontend/:  node scripts/build-data-api.js
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const SRC = path.join(ROOT, "assets", "data");
const OUT = path.join(ROOT, "data", "v1");
const SITE = "https://www.myrecon.xyz";

/** Bumped only for a breaking schema change. Additive fields do not bump it. */
const API_VERSION = 1;

/** How many entries `latest.json` carries. Sized for an embedded widget. */
const LATEST_COUNT = 10;

const CC_BY = "https://creativecommons.org/licenses/by/4.0/";

/**
 * The attribution block stamped into every breach payload.
 *
 * `required` is not decorative. CC BY 4.0 makes attribution a condition of
 * use, and the obligation runs to the upstream source.
 */
const BREACH_ATTRIBUTION = {
  required: true,
  source: "Have I Been Pwned",
  source_url: "https://haveibeenpwned.com/",
  distributor: "MyRecon",
  distributor_url: SITE,
  licence: CC_BY,
  notice:
    "Breach data originates from Have I Been Pwned and is licensed CC BY 4.0. " +
    "If you publish it you must credit Have I Been Pwned. A link to " +
    SITE +
    "/breaches/ is appreciated but not required by the licence.",
};

const CASE_ATTRIBUTION = {
  required: true,
  author: "MyRecon",
  author_url: SITE,
  notice:
    "Case file summaries are original MyRecon writing. This index may be used " +
    "to link to them. Reproducing the article text requires a visible credit " +
    "and a link to the article it came from.",
};

/** ISO date with no clock noise, so a rebuild with no change is a no-op diff. */
function today() {
  return new Date().toISOString().slice(0, 10);
}

function readJson(name) {
  return JSON.parse(fs.readFileSync(path.join(SRC, name), "utf8"));
}

function write(relPath, payload) {
  const dest = path.join(OUT, relPath);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  // Two-space JSON rather than minified. These files are read by people
  // deciding whether to use them, and a wall of one-line JSON is a reason
  // not to. Vercel serves them gzipped, so the indentation costs nothing
  // over the wire.
  fs.writeFileSync(dest, JSON.stringify(payload, null, 2) + "\n", "utf8");
  return Buffer.byteLength(JSON.stringify(payload));
}

/** The envelope every endpoint shares, so a consumer can write one parser. */
function envelope(extra) {
  return {
    api_version: API_VERSION,
    generated: today(),
    documentation: `${SITE}/developers.html`,
    ...extra,
  };
}

function main() {
  const breachSrc = readJson("breaches.json");
  const caseSrc = readJson("case-files.json");
  const breaches = breachSrc.breaches || [];
  const cases = caseSrc.cases || [];

  fs.rmSync(OUT, { recursive: true, force: true });

  // ── Individual breaches ────────────────────────────────────────────
  // One file per breach so a consumer rendering a single incident fetches a
  // few hundred bytes instead of the whole archive.
  let perBreachBytes = 0;
  for (const b of breaches) {
    perBreachBytes += write(
      path.join("breaches", `${b.slug}.json`),
      envelope({
        licence: CC_BY,
        attribution: BREACH_ATTRIBUTION,
        breach: b,
      })
    );
  }

  // ── The full feed ──────────────────────────────────────────────────
  write(
    "breaches.json",
    envelope({
      licence: CC_BY,
      attribution: BREACH_ATTRIBUTION,
      count: breaches.length,
      total_accounts: breachSrc.total_accounts,
      breaches,
    })
  );

  // ── Latest N, newest first ─────────────────────────────────────────
  // Sorted by when the breach was added to the archive rather than when it
  // occurred: a breach disclosed in 2019 and loaded last week is new *to a
  // reader*, and a widget showing "latest" means latest news, not latest
  // incident date.
  const latest = [...breaches]
    .sort((a, b) => String(b.added_date || "").localeCompare(String(a.added_date || "")))
    .slice(0, LATEST_COUNT);
  write(
    "latest.json",
    envelope({
      licence: CC_BY,
      attribution: BREACH_ATTRIBUTION,
      count: latest.length,
      breaches: latest,
    })
  );

  // ── Case file index ────────────────────────────────────────────────
  // Metadata and a link, never the article body. The writing is ours and
  // republishing it wholesale is not what this endpoint is for.
  write(
    "case-files.json",
    envelope({
      licence: "All rights reserved. Index may be used to link to the articles.",
      attribution: CASE_ATTRIBUTION,
      count: cases.length,
      case_files: cases.map((c) => ({
        slug: c.slug,
        url: c.url,
        headline: c.headline,
        subject: c.subject,
        description: c.description,
        occurred: c.occurred,
        disclosed: c.disclosed,
        people_count: c.people_count,
        vector: c.vector,
        exposed: c.exposed,
        published: c.published,
        updated: c.updated,
        reading_minutes: c.reading_minutes,
      })),
    })
  );

  // ── Headline numbers ───────────────────────────────────────────────
  // Exists so an embed can render a single counter without pulling the
  // archive. Also the cheapest possible health check.
  const severe = breaches.filter((b) => b.band === "Severe").length;
  const stealer = breaches.filter((b) => b.stealer_log).length;
  const verified = breaches.filter((b) => b.verified).length;
  write(
    "stats.json",
    envelope({
      licence: CC_BY,
      attribution: BREACH_ATTRIBUTION,
      breaches_tracked: breaches.length,
      accounts_affected: breachSrc.total_accounts,
      severe_breaches: severe,
      stealer_log_breaches: stealer,
      verified_breaches: verified,
      case_files: cases.length,
      case_file_words: caseSrc.words,
    })
  );

  // ── Discovery root ─────────────────────────────────────────────────
  // Every endpoint listed from one place, so a developer who finds any URL
  // can find the rest without the documentation page.
  write(
    "index.json",
    envelope({
      name: "MyRecon public data API",
      description:
        "Data breach metadata and case-file index, free and keyless. " +
        "No account, no API key, no rate limit beyond ordinary fair use.",
      licence: CC_BY,
      attribution: BREACH_ATTRIBUTION,
      endpoints: {
        breaches: `${SITE}/data/v1/breaches.json`,
        breach_by_slug: `${SITE}/data/v1/breaches/{slug}.json`,
        latest: `${SITE}/data/v1/latest.json`,
        case_files: `${SITE}/data/v1/case-files.json`,
        stats: `${SITE}/data/v1/stats.json`,
      },
      embed: `${SITE}/assets/js/embed.js`,
      counts: { breaches: breaches.length, case_files: cases.length },
    })
  );

  console.log(
    `[data-api] v${API_VERSION}: ${breaches.length} breaches ` +
      `(${(perBreachBytes / 1024).toFixed(0)} KB across per-slug files), ` +
      `${cases.length} case files, 5 collection endpoints`
  );
}

main();
