# Extended scans on a small Render instance

The web service previously ran two Gunicorn workers with two heavy scan slots
each. Extended scans used 96 probe threads per scan. Four simultaneous scans
could therefore create 384 probe threads, in addition to HTTP and enrichment
threads, on the same instance. CPU saturation alone does not identify a crash:
check Render logs for worker timeouts, out-of-memory kills, or exceptions.

## Small-instance configuration

Use the start command in `backend/render.yaml` and `backend/Procfile`:

```
gunicorn wsgi:app --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:$PORT
```

Set these Render environment variables (existing dashboard overrides must also
be updated; editing the repository does not change an existing manual service):

| Variable | Value |
| --- | --- |
| FULL_SCAN_SLOTS | 1 |
| SWEEP_CONCURRENCY | 8 |
| FULL_SCAN_DEADLINE_SECONDS | 300 |
| EXTENDED_SCAN_DEADLINE_SECONDS | 1800 |

The semaphore is process-local. Keep one Gunicorn worker and one service
instance for this configuration to enforce a single heavy scan across HTTP
threads. Other endpoint workloads still share the CPU.

The sweep retains every platform and submits only the active probe window.
Progress streams and queued requests send events at least every five seconds.
The browser allows seven minutes for Full scans and 32 minutes for Extended
scans, including time spent queued and enriching results. A disconnected stream
cancels further sweep work and retains the slot until active requests finish.
Active DNS/HTTP calls cannot be interrupted immediately. An admitted running
scan still consumes its allowance when the client disconnects; a queued scan
closed before acquiring a slot is refunded.

Budget exhaustion reports unchecked platforms as unknown and marks the report
partial, preventing an incomplete sweep from entering the successful-result
cache. Blocks and provider outages still remain unknown rather than absent.

## Verify after deployment

Confirm the running start command and environment settings, then run a single
Extended scan. Check that `coverage.unchecked` is zero, platform checks include
the entire catalogue, health requests remain responsive, and Render does not
restart the worker. Observe peak memory and CPU throughout the run. Repeat with
a second queued client and with a disconnected client. Local fixture tests
verify scheduling and cancellation, not real provider coverage or Render CPU.

This configuration reduces resource pressure but cannot guarantee every
provider is reachable or that every scan finishes within 30 minutes on 0.1 CPU.
Increasing only the timeout does not increase compute capacity.

## Durable completion across restarts

For scans that must survive tab closure, deployment, or worker crashes, move
Extended scans to a persistent job queue and a separate background worker.
Store per-platform checkpoints, resume only unfinished checks, and keep credit
charging/refunding idempotent using the job ID. The API returns a job ID and the
browser polls or subscribes to stored progress. This requires additional
infrastructure and is not implemented by the small-instance fix.

Render documents its worker/queue model at
https://render.com/docs/background-workers and free-service limitations at
https://render.com/docs/free.
