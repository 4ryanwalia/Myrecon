# Profile links in the existing username search

Local implementation only. No deployment or publication.

## Supported inputs

- Plain usernames and one leading @, submitted normally.
- Instagram: instagram.com and www.instagram.com, /handle with optional trailing slash.
- TikTok: tiktok.com and www.tiktok.com, /@handle with optional trailing slash.
- GitHub: github.com and www.github.com, /handle with optional trailing slash.
- HTTP(S) only. Canonical source URLs use HTTPS and omit query parameters/fragments.
- Conservative platform-specific ASCII handle syntax and a reserved-route denylist derived from the existing profile URL catalogue. Encoded routes, credentials, nondefault ports, nested paths, dot segments and lookalike hosts are rejected.

No user-supplied URL is fetched by these parsers. Post/reel/video author resolution and short-link expansion are deliberately unsupported; the UI asks for a full profile link. Existing URL safety tooling is not reused as a redirect resolver because it does not establish this input boundary's required per-hop guarantees.

## Behaviour

The existing website run action and Android lookup action handle the extracted username. Existing entitlement checks, scan limits, ad handling, result streaming, and unknown/incomplete outcomes remain in place. Before You Meet selects this same username tool. Pasting a recognized profile schedules submission after 700 ms, with edit/cancel controls. Ordinary typing and plain handles require submission. Android uses bulk text insertion/replacement detection for paste, and ACTION_SEND uses the same parser. Multiple shared links stay in the field for correction; they never auto-submit.

Source profile labels explicitly say user supplied, not verified. Handle matches say Same username and do not establish identity. No dating score or relationship inference was added. Source context is shown in the active lookup; it is not persisted into historical report schemas.

## Changed files

Website:
- frontend/assets/js/profile-input.js
- frontend/assets/js/app.js
- frontend/assets/js/username-search-input.js
- frontend/index.html
- frontend/app.html
- frontend/tests/profile-input.test.cjs
- frontend/tests/profile-input-browser.cjs

Backend:
- backend/core/profile_input.py
- backend/core/validation.py
- backend/tests/test_profile_input.py

Android (ignored by existing Git configuration; preserve explicitly when preparing a commit):
- app/src/main/java/com/aryan/myrecon/data/ProfileInput.kt
- app/src/main/java/com/aryan/myrecon/SharedInput.kt
- app/src/main/java/com/aryan/myrecon/MainActivity.kt
- app/src/main/java/com/aryan/myrecon/ui/screens/LookupViewModel.kt
- app/src/main/java/com/aryan/myrecon/ui/screens/LookupScreen.kt
- app/src/main/java/com/aryan/myrecon/ui/screens/ResultViews.kt
- app/src/test/java/com/aryan/myrecon/ProfileInputTest.kt
- app/src/androidTest/java/com/aryan/myrecon/ProfileShareTest.kt

Documentation: this file and docs/android-share-to-myrecon.md.

Lifecycle verification also required guarding an absent splash icon in MainActivity. A concurrently added Last checked label in LookupScreen was made null-safe without removing it.

## Verification

- Backend: 148 passed across profile input, username stream and username integration tests.
- Node: 29 passed across profile input and existing username integration rendering tests.
- Browser: focused local fixtures cover paste, tracking removal, duplicates, ambiguity, cancel, manual submit, mobile width, guest full-scan gating, live streaming cards and duplicate Enter suppression. No live provider requests.
- Android: debug APK, instrumentation APK and 13 targeted JVM tests passed using an isolated build directory. Offline Android 16 emulator lifecycle test passed: cold ACTION_SEND, warm ACTION_SEND, multiple-link correction, and edited draft retained through recreation. The initial splash-icon crash was fixed and the final assembleDebug plus connectedDebugAndroidTest run passed. Temporary emulator storage-reserve settings were restored.
- Existing guest-access-browser.cjs timed out waiting for #scanLog, an element absent from the current pre-existing results UI. Its preceding guest/authenticated scan checks passed; the focused new test checks live cards instead.
- No physical-device testing or real Instagram/TikTok/GitHub provider verification was performed.
