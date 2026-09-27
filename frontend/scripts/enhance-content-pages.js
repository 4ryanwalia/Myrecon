/* Add the Android self-audit context to editorial pages after page generators run.
 * This runs only for /find, /guides, /privacy and /vs. The home tool is untouched.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PLAY_URL = "https://play.google.com/store/apps/details?id=com.Myrecon.osint";
const CONTENT_UPDATE_DATE = "2026-09-27";
const SECTIONS = ["find", "guides", "privacy", "vs"];

const details = {
  find: "Use the app for a broader self-audit of supported public usernames. Availability differs by platform, and a matching handle does not establish who owns an account.",
  guides: "Put this guide into practice with a public username self-audit on your own accounts or accounts you are authorized to review. Check every candidate at its source.",
  privacy: "Follow the official removal steps in this guide yourself. MyRecon helps you review public exposure; the app does not submit this site's deletion request for you.",
  vs: "MyRecon helps you review public username leads from supported sites. Compare each tool's current coverage and verify candidate profiles at their source.",
};

function appContext(section) {
  return `<section class="content-app-context" data-content-app-context aria-label="MyRecon Android app">
  <h2>Review your public footprint with MyRecon</h2>
  <p>${details[section]} The Android app runs a username sweep from your phone and labels uncertain checks as unknown.</p>
  <p>Core app tools are free and need no signup. The Google Play listing is in closed testing, so only eligible testers can access it until public release. <a href="${PLAY_URL}" target="_blank" rel="noopener noreferrer">View MyRecon on Google Play</a>.</p>
</section>`;
}

function mobilePromo() {
  return `<aside class="content-app-promo" data-content-app-promo aria-label="MyRecon Android app">
  <button type="button" data-app-promo-dismiss aria-label="Dismiss app invitation">×</button>
  <h2>MyRecon on Android</h2>
  <p>Check public usernames on your phone. Free, with no signup. Closed testing is open to eligible testers; public release is coming soon.</p>
  <a class="content-app-promo__link" href="${PLAY_URL}" target="_blank" rel="noopener noreferrer">View on Google Play</a>
</aside>`;
}

function enhance(file, section) {
  let html = fs.readFileSync(file, "utf8");
  if (!/<main\b/i.test(html) || /<meta\b[^>]*http-equiv=["']refresh["']/i.test(html)) return false;
  if (!html.includes("data-content-app-context")) {
    const placement = /<\/article>/i.test(html) ? /<\/article>/i : /<\/main>/i;
    html = html.replace(placement, `${appContext(section)}\n$&`);
  }
  if (!html.includes("data-content-app-promo")) {
    html = html.replace(/<\/h1>/i, `</h1>\n${mobilePromo()}`);
  }
  if (!html.includes("/assets/css/content-app-promo.css")) {
    html = html.replace(/<\/head>/i, `  <link rel="stylesheet" href="/assets/css/content-app-promo.css">\n  <link rel="stylesheet" href="/assets/css/content-app-context.css">\n</head>`);
  }
  if (!html.includes("/assets/js/content-app-promo.js")) {
    html = html.replace(/<\/body>/i, `  <script src="/assets/js/content-app-promo.js" defer></script>\n</body>`);
  }
  // The app explanation materially updates these articles. Keep newer dates
  // that an editor has assigned after this release.
  html = html.replace(/("dateModified"\s*:\s*")(\d{4}-\d{2}-\d{2})(")/g,
    (whole, before, day, after) => day < CONTENT_UPDATE_DATE ? `${before}${CONTENT_UPDATE_DATE}${after}` : whole);
  fs.writeFileSync(file, html, "utf8");
  return true;
}

let count = 0;
for (const section of SECTIONS) {
  const dir = path.join(ROOT, section);
  if (!fs.existsSync(dir)) continue;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isFile() && entry.name.endsWith(".html") && enhance(path.join(dir, entry.name), section)) count++;
  }
}
console.log(`Enhanced ${count} content pages with Android app context`);
