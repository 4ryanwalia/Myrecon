# MyRecon Android stability work — 6 November 2026

Scope: the ten Play Console crash/ANR clusters shown for 7 September–6 November 2026. Current production version inspected was 13 (1.12). Local fixes are version 14 (1.13); no Play release was submitted.

## Changes and remaining uncertainty

| Play cluster | Failure | Local change | Verification boundary |
| --- | --- | --- | --- |
| 40904595a684236ef1cc1828539aac76 | Confirmed-profile link launch, ActivityNotFoundException wrapped by AndroidUriHandler | Shared guarded HTTP(S) opener validates destinations, catches launch failures, and shows feedback. Applied to both lists and other browser-link consumers. | Actual confirmed/unverified card callbacks tested with an unavailable-browser handler. |
| a55afa99064454e3ad14c12f7424e2b2 | Unverified-profile link launch | Same shared opener. | Same regression. |
| 237a1e228e3bc8b4c87b0452ca3cb4e3 | Text-field tap focus: parameter must be a descendant | Compose UI/Foundation/runtime 1.9.2 → 1.10.6 through BOM 2026.03.01. Upstream focus rewrite bypasses the old failing FocusFinder exit path by default. | Emulator native-view/Compose focus and selection regression; affected Samsung device still needs validation. |
| 2a04849be0abd2d06743839f6c6f432a | Text selection focus: same hierarchy exception | Same Compose update. | Same device-test boundary. |
| 2b22c3e1ebf5b8049f25165daefd250e | FocusFinder null parent | Same Compose update removes the shared old exit path. | Maxwest Android 14 report was not reproduced on that physical device. |
| f32dbbf62a87b1bc31160fcec643ba1d | Configuration-change view-thread mismatch, expected LooperProvider | Replaced cold WebSettings UA initialization on IO with supported asynchronous WebView startup, then main-thread UA read; five-second suspension limit. Added Webkit 1.16.0. | This removes an unsupported initialization pattern. The Play stack has no app frames and does not prove that pattern caused the crash. Root cause remains unconfirmed. |
| 3b10a61e28979474b37e68a7267b4024 | Input timeout while main thread was drawing Compose text | Username results render replaceable pages of 12, including unverified results. External profile text is bounded before layout. Removed per-card entrance animations; stable URL/platform composition keys keep transient card state attached to the correct profile. Full counts, categories, ownership, cleanup and navigation to every result remain available. | Large-report pagination and oversized-text regressions; this is a measured-risk mitigation, not proof that the Redmi ANR has been reproduced or eliminated. |
| 3198ee68e06c4da8d91d8773f97b2023 | Old v9 screen-off broadcast ANR, main thread in Ads video code | Ads SDK 23.6.0 → 24.9.0. SDK initialization moved off main. Fixed late native no-fill callbacks loading a banner while paused; a combined lifecycle/consent gate controls requests and banner pause/resume. | Foreground/consent regressions cover the discovered race. The historical Google Ads video stall is not proven eliminated. |
| a595a5bf4169a910868ab640bc40e0e4 | Old v3 startup null pointer in splash handoff; stack unavailable | Splashscreen 1.0.1 → 1.2.0 includes the documented null-icon fix. Existing guarded icon access remains. | Repeated launch/recreation regression. Missing Play stack prevents attributing the old exception with certainty. |
| c774d4894cc8c514fd0a7fc6aa76eb2a | Honor Pad 10 Android 16 native SIGSEGV | No speculative production change. Added parallel ART URL-parser stress coverage. | **Unresolved.** Conditional local mapping identifies OkHttp URL parsing during UsernameSweep, not the cause of the native fault. Need matching production mapping/full tombstone and affected-device reproduction. |

## Tests

All 35 selected JVM tests passed (zero failures/errors): BrowserUriHandlerTest (5), ResultRenderingTest (2), AdForegroundTest (3), DevicePostureTest (8), LinkSafetyTest (10), ProfileInputTest (4), SharedInputTest (3).

All 11 selected Android instrumentation tests passed on the Android 16/API 36 x86_64 MyReconTest emulator in 116.891 seconds:

- BrowserLinkRecoveryTest: both actual profile-card lists survive unavailable-browser failure and show feedback.
- FocusInteropRegressionTest: native-to-Compose tap/selection with repeatedly replaced embedded children; removing a focused Android view with the keyboard open.
- ResultRenderingRegressionTest: a 100-profile report with oversized evidence/bio text renders bounded pages and returns to earlier results.
- StartupRegressionTest: three activity launches and three recreations through the splash path.
- SweepUrlParsingRegressionTest: catalogue profile/API URLs parsed repeatedly across eight ART worker threads without network calls.
- WebViewRuntimeTest: request startup from IO, then read the stable user agent through the main-thread path.
- LookupLayoutTest: three existing layout, light-theme and large-text dark-theme checks.
- ProfileShareTest: existing cold/warm profile sharing and recreation regression.

The completed instrumentation run's crash buffer was empty. An earlier attempt began while system boot processing and memory pressure were still high; Android killed startup before the runner began any test. Its log is retained, and it is not counted as a passing run. The settled-device rerun passed all tests without application source changes between attempts.

Debug APK and instrumentation APK builds passed. The minified `bundleRelease` build, R8, and critical release lint checks passed in 10m 58s. Both APK/AAB ZIP CRC checks passed. Version is 14 (1.13).

Artifacts:

- Debug test APK: `app/build/outputs/apk/debug/app-debug.apk`, SHA-256 `2115b24f1733eb2fd343c2aedb013fb51826ce45ba2746c147a748807c83955a`.
- **Unsigned** release AAB: `app/build/outputs/bundle/release/app-release.aab`, SHA-256 `b1ad04d65592a09f659c2e26da0c1bd8e75bdd9ab1ca2f165270862b56489c8e`. Signature inspection confirms it is unsigned. It has not been uploaded/submitted/published.
- Release validation log: `build_temp/crash-fixes-2026-11-06/gradle-release.log`.
- Source patch and SHA-256 manifests: `build_temp/crash-fixes-2026-11-06/myrecon-stability.patch`, `source-manifest.json`, `artifact-manifest.json`.

Evidence:

- `app/build/test-results/testDebugUnitTest/TEST-*.xml`
- `build_temp/crash-fixes-2026-11-06/gradle-final-debug.log`
- `build_temp/crash-fixes-2026-11-06/instrumentation-settled.log`
- `build_temp/crash-fixes-2026-11-06/emulator-settled-crash.log`
- `build_temp/crash-fixes-2026-11-06/instrumentation.log` and `emulator-first-run.log` (aborted boot-time attempt)

These tests validate the changed paths and adjacent regressions. They are not a controlled reproduction of every Play event or an independent proof of zero future crashes/ANRs on the reported OEM devices. The native fault is explicitly unresolved.

## Official implementation references

- [Focus interop rewrite](https://android.googlesource.com/platform/frameworks/support/+/749a0e8f7c3769659935ba441d5b1577aaaae520%5E%21/)
- [Core splash-screen release fixes](https://developer.android.com/jetpack/androidx/releases/core#core-splashscreen)
- [WebView startup and migration from background UA workarounds](https://developer.android.com/develop/ui/views/layout/webapps/optimize-webview-startup)
- [Ads initialization and ANR guidance](https://developers.google.com/admob/android/optimize-initialization)
- [Ads migration requirements](https://developers.google.com/admob/android/migration)
- [Compose list performance](https://developer.android.com/develop/ui/compose/lists)

## Local recovery

Pre-edit copies are saved under `build_temp/crash-fixes-2026-11-06/before`. The Android source is local-only/ignored in this checkout; no ignored files were force-added and unrelated website/backend work was preserved. A standalone patch and validation logs are packaged under `build_temp/crash-fixes-2026-11-06`.

The October 26 local v13 AAB at `app/release/app-release.aab` remains intact. Its embedded mapping SHA-256 is `75be2d85b34f569be3d5b8ab92917454cdf73def49c201dc62d01181ca2eb8c5`; copies are retained under `previous-release/` and `reference/` in the evidence folder. This preserves the conditional native retrace evidence even though the new release build replaces generated build mappings. Equality with Play's uploaded artifact is still unverified.
