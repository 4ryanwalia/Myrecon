# Production Google public profiles and reviews

The Android main app calls `POST /api/email/public-profiles` with an exact email.
The service resolves a public Google contributor through an isolated GHunt
worker and reads that contributor's public Maps reviews anonymously. It does
not run registration/recovery checks, bill scan credits, save reports or cache
results. All endpoint responses use `Cache-Control: no-store`.

The Render Blueprint uses `bash tools/build-render.sh` to install the backend
dependencies and GHunt 2.3.4 in the separate `backend/.venv/ghunt` runtime.
Both `EMAIL_GHUNT_ENABLED` and `EMAIL_GOOGLE_PUBLIC_REVIEWS_ENABLED` are enabled
in the Blueprint. Other hosts can override the default interpreter with an
absolute `GHUNT_PYTHON_EXECUTABLE` path.

For an existing Render service, apply that build command and both flags in its
dashboard. Set the hosting secret `GHUNT_SESSION_B64` to the existing contents
of the operator-authenticated GHunt `creds.m` file. GHunt already writes this
file as base64; do not encode it again. The default Windows operator login file
is `%USERPROFILE%/.malfrats/ghunt/creds.m`. Transfer its contents directly into
the hosting secret field, never into source, Android resources, logs or chat.
Alternatively, mount the file as a hosting secret and set its absolute path in
`GHUNT_SESSION_FILE`.

Deploy the changed backend. With the environment-secret option, each lookup
writes the session to a private temporary file, then removes it after the
isolated worker exits. An expired or invalid session requires a new operator
login and a refreshed hosting secret. No operator session is sent to the
anonymous Maps reader or returned to Android.

Retrieval is bounded to one page, at most 100 records for at most two established
contributors. Google may change or block its unofficial response format.
Disabled, unconfigured, authentication-required, timeout, busy and inconclusive
states remain explicit; a failed review request preserves the resolved profile.
No result claims last-seen activity or proves that unavailable reviews do not
exist.

This patch was prepared without builds or tests. Hosting deployment and manual
Android verification are separate from the source change.
