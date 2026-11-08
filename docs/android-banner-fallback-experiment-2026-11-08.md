# MyRecon main-banner fallback experiment

Status: prepared locally; not distributed and no earnings result is available.

The app assigns each installation to a persistent, random control or fallback arm. Both arms use the existing main banner. In the fallback arm only, an initial primary no-fill can trigger one request to the new `Main banner fallback experiment` AdMob unit. An already filled primary banner is not replaced after a later refresh failure. If the fallback fails or times out, the primary resumes when foreground and consent allow it. Both units use AdMob's Google-optimized automatic refresh and Google-optimized All prices floor.

## Measurement

Only users who enable the app's existing optional usage analytics emit these events. The experiment does not override that choice, and this sample can be small and unrepresentative of all users. Events contain fixed arm and placement labels, not search input or results:

- `banner_test_exposure`: an eligible foreground banner opportunity, including sessions with no ad. It may fire more than once for the same user.
- `banner_test_impression`: an SDK-reported banner impression.
- `banner_test_paid`: an impression-level ad value in `value_micros`, with `currency_code`, `precision`, `test_arm`, and `banner_role`.

Impression-level revenue is enabled in AdMob. Paid-event values can be estimated or unknown, differ from finalized earnings, and may be missing. Validate collection and precision before using them. The fallback unit's AdMob earnings show gross fallback earnings only; they do not establish incremental revenue.

The Android Firebase Analytics property is `myrecon-bugsnaps` (property 555709037). The currently signed-in account can view it but does not expose creation controls for custom definitions. Before collecting production data, an editor should register event-scoped custom dimensions for `test_arm`, `banner_role`, and `currency_code`, and an event-scoped numeric custom metric for `value_micros`. Check GA4 limits and reporting behavior; definitions do not backfill historical events. MyRecon is not currently linked to Firebase in AdMob; do not assume AdMob user metrics are available.

For each arm, count unique opted-in users with `banner_test_exposure`, including users with no impressions. Divide summed primary-plus-fallback paid micros by that unique-user denominator and by 1,000,000, separately per currency. Compare impressions per exposed user and primary/fallback counts too. Check sample sizes, country mix, uncertainty, total app earnings, and retention; do not treat raw event counts as user counts or extrapolate this opt-in sample to the entire audience without qualification. Allow multiple comparable weeks and more time if results are inconclusive. Test ads have no usable revenue and cannot establish a lift.

## Release and validation

The Android project is ignored by Git in this checkout and also contains earlier unpublished stability changes. A real earnings test needs a newly built release signed by the existing Play upload key, distribution to users, reporting access, and time for data to accrue. Review the combined release before distribution. The prior local AAB was unsigned and predates this experiment; it is not an experiment release. Verify the current Play version and signing certificate before upload.

Local tests of the state transitions are not a substitute for a connected-device test of AdView attachment, no-fill, automatic refresh, background/foreground, consent changes, timeout, and delayed callbacks. Use Google test ads on test devices.
