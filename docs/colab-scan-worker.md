# Colab primary scan worker with Render fallback

Status: implementation is opt-in and disabled by default. Local tests are not
proof of Colab availability, Firebase quotas or production crash prevention.

## What moves

Standard, Full and Extended username platform checks run on a manually started
CPU notebook when it claims a job first. Render keeps authentication, scan
allowances, payment keys, optional Google search, enrichment, exposure checks,
report assembly and history. Other lookup tools and on-device Android scanning
are not moved by this change. No Firebase or payment credential enters Colab.

Render initially gives Colab 20 seconds to claim a queued job. If no worker
claims it, one Render fallback runs the same platform checks with eight active
probes. A disconnected Colab attempt loses its lease after 90 seconds. Render
then resumes the committed platforms; probes in the last unsaved batch can be
repeated. Late results from the previous lease are refused. A notebook exception
releases its job for immediate fallback. Render also performs finalization one
job at a time, sharing the heavy-work slot with Deep Search.

This is not a 24-hour Colab hosting service. Start the notebook manually, use CPU
only, and respect session/compute limits. There are no tunnels, public notebook
servers, simulated browser interactions or attempts to evade Colab idle limits.
Google's policies distinguish interactive compute and paid compute-unit access
from unrelated web-service hosting. Confirm the intended workload fits your
account's current terms before enabling public traffic:
[Colab FAQ](https://research.google.com/colaboratory/faq.html).

## 1. Prepare Render

Deploy the matching backend code with this effective start command:

```text
gunicorn wsgi:app --workers 1 --threads 16 --timeout 120 --bind 0.0.0.0:$PORT
```

Do not copy the existing Firebase, Google, PayPal, Razorpay or other provider
secrets into the notebook. Keep the existing `FIREBASE_SERVICE_ACCOUNT`,
`FIREBASE_DB_URL`, authentication and billing settings on Render. The production
worker queue refuses to run against the development memory store. `/web` must
remain denied to browser/Firebase clients; the worker accesses it only through
the authenticated Render endpoints.

Generate a new random worker token of at least 32 characters using your password
manager or `secrets.token_urlsafe(48)` locally. Enter it as `SCAN_WORKER_TOKEN` in
Render's secret environment settings. Do not commit it, paste it into chat, save
it in notebook code or share notebook outputs containing it.

Set these non-secret values:

```dotenv
SCAN_OFFLOAD_ENABLED=true
FULL_SCAN_SLOTS=1
SWEEP_CONCURRENCY=8
SCAN_JOB_LIMIT=4
SCAN_LEASE_SECONDS=90
SCAN_WORKER_WAIT_SECONDS=20
SCAN_JOB_TTL_SECONDS=86400
SWEEP_FULL_DEADLINE_SECONDS=300
SWEEP_EXTENDED_DEADLINE_SECONDS=1800
```

Offloaded admission is transactional and idempotent for a given request ID,
identity and scan parameters. Retrying with a new request ID is a new scan.
If temporary job data has expired but its billing receipt remains, replaying
that request returns 410; it cannot reuse the receipt for another execution.
An interrupted database write after charging retains the admitting job for
recovery by a retry or coordinator maintenance.
Final failed/cancelled jobs refund an account's reservation once. Guests retain
the existing daily-counter behavior. Cached Extended reports retain the existing
policy: require an available credit without consuming it.

Update the frontend at the same rollout so its longer scan timeout and safe GET
reconnect support are available. Deploy the accompanying privacy disclosure
before enabling external processing. Keep the flag false until deployment and
configuration are ready.

## 2. Build the matching notebook and bundle

From the repository root:

```text
python backend/tools/build_colab_bundle.py
```

The output is in `output/colab-worker/`:

- `MyRecon CPU Scan Worker.ipynb`
- `myrecon-colab-worker.zip`
- `SHA256.txt`

The allowlisted ZIP includes only the scanner engine, fixed platform catalogues,
network guard and worker client. It excludes `.env`, service accounts, repository
history, payments and server configuration. The notebook checks the ZIP's hash
before extracting it. Rebuild both files whenever the scanner changes; a worker
with a different engine/catalogue fingerprint will not receive jobs. Worker and
server use the same fingerprint despite Windows/Linux line-ending differences.

## 3. Start Colab

1. Upload/open the notebook in your existing signed-in Colab account.
2. Select **Runtime > Change runtime type > CPU**. No GPU is useful here.
3. Run the dependency cell and the CPU/RAM diagnostics.
4. Open the Files sidebar, use **Upload to session storage** to upload the
   matching worker ZIP, then run the bundle verification cell.
5. In the worker cell enter your Render API origin, for example
   `https://myrecon.onrender.com`. No path, token or query string belongs in it.
6. Enter the dedicated worker token in the hidden prompt. The token is held in
   runtime memory and is not inserted into the notebook source or outputs.
7. Leave the worker cell executing during this manually started session. It
   runs one scan at a time and defaults to 16 concurrent platform probes.
8. Stop the cell to disconnect; interrupted work is released when possible and
   otherwise recovered after lease expiry. Restart manually for another session.

You may save the notebook and ZIP in a private Drive folder for later reuse.
The notebook does not require granting access to your entire Drive. Drive
stores the files; the Colab VM performs the work. Data transfer and Firebase
usage still have quotas even when your Colab compute is included in AI Pro.

## 4. Verify the full path

Start with one known Standard scan, then Full and Extended on an account with
allowance. Check:

- Colab claims the job and upload acknowledgements succeed.
- The public stream shows progress, found cards and a final report.
- The report's platform count and uncertainty match the scanner evidence.
- Guest Full reports reveal only the public catalogue preview.
- Paid credits and free allowances change only once per job.
- Signed-in reports appear in history once, including after reconnect/restart.
- Render's effective command has one process; CPU, memory and other lookups
  remain usable while Colab works.

Then stop the Colab worker during an Extended scan after progress has uploaded.
Verify Render resumes the same job after lease expiry, preserves committed
checks and does not charge it again. Test Colab absent from the start, a dropped
browser stream, Render restart, explicit cancellation and a failed provider.
Compare real elapsed time and coverage before claiming any speed improvement.
Cloud provider IP ranges can change which platforms block or answer a request.

## Recovery API

The first NDJSON event for an uncached offloaded scan is:

```json
{"type":"job","job_id":"<opaque id>","resumable":true}
```

Existing POST bodies may include a random `request_id` (16 to 80 letters,
digits, hyphens or underscores). The website generates one automatically and
reconnects once to the same job after a dropped stream. Other clients can use:

- `GET /api/username/jobs/<id>` for status and the completed report.
- `GET /api/username/jobs/<id>/stream` to replay progress/checkpoints and wait.
- `DELETE /api/username/jobs/<id>` for explicit cancellation.

Signed-in access requires the same Firebase user. Guest access is bound to the
same resolved IP and an unpredictable job ID; changing networks can prevent
guest resume. Closing a tab does not cancel or refund a running job. Signed-in
users can reopen the completed report from history. The frontend does not start
a new charged scan automatically when a reconnect fails.

## Limits and rollback

- Four admitted jobs at once by default; excess requests receive 429 before
  admission. Configure no more than eight so HTTP worker requests retain room.
- At most 256 retained jobs in the dispatcher; cleanup removes terminal jobs
  after the configured 24-hour retention when the coordinator next runs.
- Unfinished jobs expire after one hour and failed account reservations are
  refunded. Render fallback may queue or produce a partial report under load.
- Full/Extended deadline omissions remain `unknown`, with `coverage.unchecked`
  and `partial=true`; they are never cached as a complete scan.
- Billing receipts are retained for two days and cleaned during subsequent
  admission. Signed-in history follows the existing newest-50-report policy.
- Persistent checkpoints, identifiers and temporary results live in the
  server-managed Firebase database. The notebook does not write scan data to
  Drive automatically or log queried usernames.
- There is no promise of unlimited free capacity, guaranteed performance or
  zero crashes. Durable fallback reduces dependency on a Colab session.

To roll back, set `SCAN_OFFLOAD_ENABLED=false` on Render and stop the notebook.
New requests use the original API paths with the reduced Render concurrency.
Existing offloaded jobs are retained but stop progressing until the coordinator
is re-enabled, so finish/cancel them before rollback where possible.
