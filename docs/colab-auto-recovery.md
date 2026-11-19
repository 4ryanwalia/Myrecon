# Colab CPU recovery from the existing Render service

Status: opt-in; disabled unless explicitly enabled and authorized. Included
compute units are consumed, but this code never purchases units or upgrades a
plan. Existing scan fallbacks remain in place. This is best-effort recovery,
not uninterrupted hosting or zero startup time.

## Verified account context (2026-11-08)

Colab Settings > Subscription recognizes Google AI Pro. Resources showed 393.3
available compute units and approximately 0.08 units/hour for one standard CPU
runtime. This is one observed rate, not a fixed price or guaranteed entitlement.
Storage capacity alone does not establish compute entitlement. Promotional
Google AI trials may not include Colab compute benefits.

## Behavior

`wsgi.py` starts a supervisor only when `COLAB_AUTO_RECOVERY_ENABLED=true`,
RTDB-backed worker coordination is available and Google credentials are configured.
The supervisor shares the existing Render service; no second free service or
paid worker is created. A transactional 120-second RTDB lease excludes other
Gunicorn workers and overlapping deployments. It is renewed every 40 seconds.
If renewal fails, the local controller process is terminated.

The child uses google-colab-cli 0.7.5 in a separate virtual environment. It
checks for a positive included compute-unit balance, requests standard CPU
only, and sends the matching source-only worker bundle plus dedicated worker
token to Colab. Firebase, payment, search and Google OAuth credentials are
never sent to the worker. The controller suppresses provider error bodies,
remote source and CLI execution histories because they can contain secrets.
The private Worker Console shows the recovery stage and the next scheduled
retry when applicable. The token-authenticated recovery endpoint reads the
same in-memory status. Only allowlisted child stage changes are logged.

An HMAC-derived stable notebook identity lets a replacement controller reclaim
its own orphaned assignment. It never stops unrelated manually opened notebooks.
After a session ends, it releases its assignment and retries with backoff.
Startup has a three-minute timeout and a running worker has a five-minute
activity timeout, both checked at the lease interval. The managed worker
reports activity from existing claim and heartbeat responses. During a Render
outage the same session backs off between attempts, up to 90 seconds, and
reports that it is still alive. Repeated Colab failures back off up to 15
minutes. An empty compute balance waits 30 minutes. Invalid Google or worker
authorization stops retries until the service restarts with corrected
credentials. The worker still has its ten-hour execution limit and the
controller process is bounded to eleven hours.

When Colab is polling, its requests provide real inbound Render traffic. If
both services are stopped, the existing `Keep API Awake` GitHub workflow can
wake Render via `/api/health`; a real user request can do the same. GitHub
schedules can be delayed or disabled, and Render can suspend free services at
its usage limit. The coordinator falls back to Render while the worker
recovers, as long as Render is available.

## Activation

1. Deploy this code using the existing `bash tools/build-render.sh` build command
   and `gunicorn wsgi:app --workers 1 --threads 16 --timeout 120 --bind 0.0.0.0:$PORT`.
   Do not use Gunicorn `--preload` (the supervisor starts in the worker).
2. Obtain explicit approval for persistent Colab account access on Render.
   In a local environment with `tools/requirements-colab-controller.txt` installed,
   run `python backend/tools/authorize_colab_controller.py --output output/private/colab-authorized-user.json`.
   Complete Google's consent with the Google AI subscriber account. The helper
   requests only user email and Colab management scopes, not Drive, Gmail or
   Cloud Platform access. Do not put auth codes, tokens or generated JSON in chat.
3. Put that JSON into Render's secret environment variable
   `COLAB_GOOGLE_CREDENTIALS_JSON`. The refresh token lets Render obtain new Google
   access tokens after the computer is off. Keep this secret out of Git, logs,
   notebooks and frontend responses.
4. Keep `SCAN_OFFLOAD_ENABLED=true` and the existing `SCAN_WORKER_TOKEN`. Set
   `COLAB_AUTO_RECOVERY_ENABLED=true`; optionally set `COLAB_API_ORIGIN` to the
   HTTPS API origin (defaults to `https://myrecon.onrender.com`). Redeploy.
5. Verify `Auto CPU worker` appears live in the private Worker Console. Run an
   authorized test scan. Terminate only the managed runtime and verify a new
   runtime appears and checks in without browser interaction. Verify one scan
   allowance, checkpoint recovery, Render memory and fallback behavior.
6. Verify again after closing the browser and with the local computer off.
   Mocked tests and a manually restored notebook do not prove these outcomes.

Disable by setting `COLAB_AUTO_RECOVERY_ENABLED=false` and redeploying. Stop
the managed runtime in Colab as well: terminating a controller process may leave
its current runtime executing until its ten-hour limit. Remove the Render
credential and revoke the Google authorization when no longer needed. Changing
`SCAN_WORKER_TOKEN` changes the managed notebook identity, so stop the prior
managed assignment before rotating it.

## Sources

- [Colab API/automation](https://github.com/googlecolab/google-colab-cli)
- [Colab limits and Google AI benefits](https://research.google.com/colaboratory/faq.html)
- [Render free instance limits](https://render.com/docs/free)
