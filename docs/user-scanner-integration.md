# Bounded User Scanner integration

The local adapter is an independent, deliberately narrowed port of selected
User Scanner endpoint/metadata mappings. Attribution and upstream paths are in
`backend/modules/user_scanner_registry.py`; the MIT notice is in
`docs/licenses/user-scanner-MIT.txt`. Reference code is never loaded at runtime.

Only `username.github` and `email.gravatar` are registered. Both are disabled.
There is no user-facing module selector, filesystem discovery, new endpoint,
upstream catalogue import, installer, CLI invocation or automatic cross-scan.
Registry additions and enabling entries require a reviewed code change.

`scan_selected(target, scan_type, module_ids=None, permitted=False)` is an
internal service API. A caller must first apply its existing authentication,
entitlement, scan-credit, target-validation and scope gates. Do not expose
`permitted` or module paths as request parameters. Registry selection does not
authorize scans. Existing services expose skipped diagnostics while disabled.
Use `username_contract` / `email_contract` to project results when wiring future
selected modules; merge only confirmed profiles and keep all diagnostic rows.
Do not replace Sweep verdicts with optional errors, or cache partial outcomes.

Two process-wide worker slots, at most two selected modules, sequential module
execution, a 20-second scan deadline and a 9-second hard per-process deadline
bound work. Parent kills and reaps timed-out workers. Requests have bounded
connect/read timeouts, guarded/pinned DNS, rejected redirects, exact host
allowlists, a 256 KiB body cap and a 16 KiB output cap. No retries, proxy
configuration, cookies, authentication, arbitrary URLs or media fetching.
Input travels through stdin; stderr and exception text are discarded.

Found and explicit negative evidence map to Sweep found/not_found. Other
statuses map to unknown while preserving unavailable, skipped, rate_limited
and timeout in `status`, alongside source and reason. Email no_match is a
source-specific negative signal, never proof that no account exists. Gravatar
404s currently remain unavailable because readable profile absence is not
registration absence. Missing requests/transport imports produce unavailable.
Only declared scalar public metadata survives; no email addresses, phone
numbers, provider bodies, nested data, recovery fragments or harvested links.

No dependency was added. No runtime validation was performed for this change.
