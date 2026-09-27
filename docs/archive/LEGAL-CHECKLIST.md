# Legal & compliance — what still needs you

> Historical working checklist from September 2026. This is not a current
> compliance assessment: site copy, placeholders, payment terms, and provider
> settings may have changed. Verify the live site and dashboards before acting
> on any item below.

The privacy policy, terms of use and cookie policy are written and wired into
every page. The items below are the ones that cannot be settled from the
codebase, ordered by how much they matter.

---

## 1. Fill in the placeholders — blocking

Six visible amber `FILL IN: city` badges are on the site right now, and they
are deliberately loud so they cannot ship unnoticed.

```bash
grep -rn "legal-todo" frontend/*.html
```

| File | Occurrences | What it is |
| --- | --- | --- |
| `frontend/privacy.html` | 3 | Principal place of business, Grievance Officer address, contact block |
| `frontend/terms.html` | 3 | Operator address, Grievance Officer address, **court of jurisdiction** |

Replace each `<span class="legal-todo">FILL IN: city</span>` with your city.
The jurisdiction clause in the terms should name the courts where you actually
operate — that is the one with real consequences if a dispute ever happens.

You chose to publish city + country rather than a full postal address. That is
a reasonable minimum for a sole proprietor. Note that India's Consumer
Protection (E-Commerce) Rules 2020 expect a **principal geographic address**
from anyone selling to consumers, which the paid report service is — see item 5.

---

## 2. Turn on Google's certified consent message — blocking for EEA/UK ads

This is a dashboard setting, not code, and the site's cookie policy states that
it is in place. **Confirm it actually is**, or the policy is inaccurate.

1. AdSense → **Privacy & messaging** → **European regulations**
2. Confirm a GDPR message is **published** and live for `myrecon.xyz`
3. While there, publish the **US states** message too — that is the operational
   half of the Global Privacy Control statement in the privacy policy
4. Do the same under AdMob for the Android app

**The Android half is now wired up (16 September 2026).** The UMP SDK had been
a dependency that nothing ever called — so no consent message could appear in
the app at all, whatever was published in the dashboard. `ads/Consent.kt` now
runs it before any ad request, and `Ads.awaitReady` will not return for a user
whose choice forbids ads, so both ad surfaces are covered by one gate. A
standing "Ad privacy choices" row lives in the app's privacy sheet for anyone
Google says must be able to reopen their choice.

That makes step 4 above the blocking half: **the SDK shows whatever is
published, and if nothing is published, nothing appears.** To see the form
before submitting, put the handset's hashed ID into `TEST_DEVICE_HASHED_IDS` in
`ads/Consent.kt` — it forces the EEA form in debug builds, which is the only
way to test this from India.

We deliberately did **not** build a cookie banner. Google requires a
Google-certified CMP for ads served in the EEA, UK and Switzerland, so a
home-made banner would not be a valid consent basis — it would just be a
second prompt in front of the real one. `frontend/assets/js/consent.js`
instead reopens Google's own message, and falls back to linking the cookie
policy where no CMP is present, so the control is never a dead button.

---

## 3. Play Store Data Safety form must match

`play-store/LISTING.md` points Play at `https://myrecon.xyz/privacy.html`, so
that policy is now the app's policy. Section 16 was written from the actual
code and declares: AdMob advertising including rewarded ads and the advertising
ID, camera used for QR scanning with no image upload, notifications, on-device
storage, the address-disclosing lookups, and device-IP contact with the
platforms being swept.

Re-open the Data Safety form and confirm every one of those is declared. The
listing file itself says this form must match the code exactly.

**`play-store/LISTING.md` §5 now carries the finished answers** — every data
type, whether it is collected, shared, required or optional, and the file each
was read from. Two things it settles that had been left open, both verified in
the build: the app **does** contain ads, so "no ads" and "collects nothing" are
both wrong answers; and the merged manifest carries
`com.google.android.gms.permission.AD_ID`, so the Advertising ID declaration is
not optional either.

Three services were missing from section 16 of the policy and were added on
16 September 2026, because the Data Safety answers now point at them: the
**MyRecon API fallback** (`myrecon.onrender.com`, used when a direct lookup is
refused), **`ipwho.is` and `cloudflare-dns.com`** for the self-scan, and the
Deep Search engines and registries. The same facts are stated in the app's own
privacy sheet, in plain language.

Three of these were corrected on a re-check and are easy to get wrong on the
form too, so verify them against the source rather than from memory:

| Thing | What the code actually does | Where |
| --- | --- | --- |
| Camera | **QR code scanner**, not photo capture. Photos come from the system picker. | `ScanScreen.kt`, `ImageScreen.kt` |
| QR scanning | **Not purely on-device** — follows the link's redirects and does an RDAP lookup on the destination | `LinkSafety.kt` |
| Per-address breach check | Sends the address to **leakcheck.io** | `AccountBreachCheck.kt` |
| In-app email lookup | Sends the address to **api.xposedornot.com**, in the URL query string | `OnDeviceIntel.kt` |

Full set of services the app contacts, besides the username-sweep targets:
`leakcheck.io`, `api.xposedornot.com`, `haveibeenpwned.com`,
`api.pwnedpasswords.com`, `rdap.org`, `api.certspotter.com`, `api.github.com`,
`ipwho.is`, `cloudflare-dns.com`, `lite.duckduckgo.com`, `www.bing.com`,
`www.wikidata.org`, `pub.orcid.org`, `myrecon.onrender.com` (fallback only),
and this site's own breach feed.

One more Play requirement, now met: the User Data policy wants the privacy
policy reachable **inside** an app that touches sensitive data, not only on the
store listing. There was no link anywhere in the app. The shield in the app bar
opens a sheet with the policy, the terms and the ad choices
(`ui/components/PrivacySheet.kt`), and the last onboarding page links to the
policy too.

---

## 4. Google Fonts — an open EU exposure, your call

Every page loads Inter from `fonts.googleapis.com` / `fonts.gstatic.com`, which
discloses visitor IPs to Google. German courts have found this an unlawful
transfer absent consent (LG München I, 2022), and it is a recurring complaint
target across the EU. It is disclosed honestly in the cookie policy, so nothing
is hidden — but disclosure is not the same as a lawful basis.

Self-hosting the font removes the issue entirely and is a contained change:
drop the woff2 files into `frontend/assets/fonts/`, replace the two
`<link>` tags with an `@font-face` block, keep the same `--font` stack. Worth
doing if EU traffic matters to you. I have not done it because it touches the
first-paint/CLS work already tuned on every page and deserves its own change.

---

## 5. The paid report service has no commercial terms — your decision

You chose to keep the terms to the free tool. Recording the trade-off so it is
a decision and not an oversight: `contact.html` and `services.html` sell a paid
personal report, which makes India's Consumer Protection (E-Commerce) Rules
2020 apply — they expect published seller details, a grievance officer (you
have one), and a stated **refund and cancellation policy**. That last one is
not on the site.

Lowest-effort fix if you change your mind: a short "How paid reports work"
section in the terms covering scope, that reports are individually quoted,
proof of ownership of the identifiers, and cancellation/refund.

---

## 6. Ads can appear on the results page — decide which way you want it

The site had been saying "advertising is never shown alongside the results of a
lookup you ran". The code does not guarantee that, so the wording has been
corrected rather than left as a promise the site might break.

Why: there is **not a single `<ins class="adsbygoogle">` unit anywhere** in the
repo, so the site runs on **Auto ads** — Google's script is on the page and
Google decides placement. `index.html` is both the lookup tool and where
`#results` renders, and it loads that script. So Google may legitimately place
an ad next to your results.

What the policies now say instead, all of which is verifiable: nothing you type
is passed to any advertising system, ads are selected from the page's published
content rather than from your query, and the policy pages, contact page and
Deep Search carry no advertising at all.

If you would rather the original promise were true, either:

- **Remove the AdSense script from `index.html`** — cleanest, costs you ad
  revenue on your highest-traffic page; or
- **Turn Auto ads off for that page** in AdSense and place manual `<ins>` units
  deliberately, none of them near `#results`.

Do either and the stronger wording can go back. Pages carrying ads today:
`index.html`, `about.html`, `app.html`, `services.html`, `founder.html`, all of
`guides/`, and all of `breaches/`.

---

## 7. Smaller things worth knowing

- **Two theme keys.** `app.js` uses `myrecon-theme`, `deep-search.js` uses
  `myrecon.theme`, so the theme does not carry between Deep Search and the rest
  of the site. Both are documented accurately in the cookie policy. Unifying
  them is a one-line fix that resets one stored preference once — not done here
  because it is a behaviour change outside this task.
- **Review dates.** Both policies say "Last updated: 14 September 2026". Change
  it whenever you change the substance, not just the wording.
- **`.legal-todo` is a shipping guard.** Anything wrapped in it renders as a
  bright amber badge. Keep using it for anything provisional.

---

## What was already done

A second pass re-checked every factual claim against the source and corrected
five things: the advertising-placement promise above; "MyRecon sets no cookies
of its own", which contradicted our own table (Google's script sets some under
the myrecon.xyz name); a bare "we honour Global Privacy Control" claim with no
implementation behind it; the app's camera and per-address-check descriptions
(item 3); and a subprocessor table that hid XposedOrNot, LeakCheck, GitHub and
Gravatar under "public data sources".

Written and live in this change: the rewritten privacy policy (18 sections,
including India DPDP + grievance officer, GDPR/UK legal bases and rights,
CCPA/CPRA, children, an Android app section and a "if you were searched for"
section), the rewritten terms (19 sections, including governing law, takedowns,
an anti-discrimination clause and a liability cap), a new cookie policy, the
consent-reopening control on every page, consent wording on the breach-check
forms, `referrerpolicy="no-referrer"` on the HIBP logos, and the accessibility
and contrast fixes listed in the change summary.
