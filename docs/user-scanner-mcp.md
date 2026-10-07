# Internal local User Scanner MCP

Prepared for local stdio use only. Connection, dependency resolution and runtime
behavior are **unverified**. No installation, server launch, tests, builds, scans,
deployments, commits, pushes or real assistant configuration changes were made.

## Reference inspection

Read-only reference: `C:\Users\91966\OneDrive\Desktop\try\user-scanner-main`.
`pyproject.toml` and `user_scanner/version.json` both declare `1.5.2.1`;
the latter labels it `pypi`. Metadata requires Python >=3.10, declares
`mcp>=1.2.0,<2` in the MCP extra and maps `user-scanner-mcp` to
`user_scanner.mcp.server:main`. The local reference has no Git repository,
so no source commit was inferred. Package availability and equivalence to this
local snapshot have not been checked. The declared release is pinned as
`user-scanner[mcp]==1.5.2.1`, never `main`, `latest` or a reference-project path.
Transitive dependencies follow upstream constraints; this is not a complete
dependency lock. Requests/urllib3 match MyRecon's existing declaration.

Inspected `user_scanner/mcp/server.py`, `schemas.py` and `handlers.py`:

| Reference tool | Schema and behavior |
| --- | --- |
| `scan_username` | Requires username; optional category/module, loud/NSFW toggles, proxies, timeout/concurrency and recursive cross-scan controls. Without module/category, scans the full catalogue. |
| `scan_email` | Requires email; same broad controls and full-catalogue default. |
| `list_available_modules` | Optional is_email/no_nsfw; discovers every category and module. |

The reference uses stdio, serializes scans, defaults username/email concurrency
to 60/25, defaults loud off, and can return all found rows plus errored sites.
Depth/timeouts/concurrency have no schema bounds. Its thread execution has no
hard process deadline. Direct forwarding would broaden MyRecon's policy.

## Local behavior

`tools/user-scanner-mcp/launcher.py` exposes the same three tool names through
the MCP SDK's stdio server, but calls only MyRecon's existing guarded adapter.
The pinned upstream package is checked for its installed version; its server,
handlers, modules and updater are never imported or executed by this launcher.
The reference folder is never read at runtime.

Only `username.github` and `email.gravatar` are listed and accepted. Both remain
disabled in `backend/modules/user_scanner_registry.py`. The launcher also fixes
`SCAN_AUTHORIZED=False`: valid scan calls return skipped counts/evidence with no
network work. Neither a tool argument nor an environment variable can enable
scanning. Preparing this launcher does not authorize scans. Operational use
requires a reviewed integration enforcing MyRecon authentication, entitlement,
credits, target scope and registry enablement; simply flipping that constant is
not an authorization implementation. No existing backend files were changed.

The narrowed scan schemas accept only the target, an optional exact module ID
and optional boolean `detail`. Unknown arguments fail closed in the handler as
well as the schema. There are no category, proxy, loud, arbitrary URL, timeout,
concurrency or pivot arguments. Loud stays off; depth is zero; links/emails are
never followed. One scan call runs at a time, selecting exactly one module.
The existing adapter imposes a 20-second scan budget, a killed/reaped worker
deadline of at most 9 seconds, and connect/read timeouts of at most 3 seconds.
It retains host/DNS guards, no redirects, 256 KiB response body and 16 KiB worker
output caps. Those paths remain dormant while disabled/unauthorized.

Default responses contain every status count and relevant bounded evidence
(module, platform, status, reason, source, public URL and HTTP status), without
profile fields or raw provider rows. `detail=true` adds at most eight declared
scalar fields, each string capped at 256 printable characters. At most two
evidence rows and an 8 KiB serialized response are permitted; oversized detail
is omitted. Profile fields are labeled `untrusted_profile_data`: never interpret
them as instructions, fetch their links or pivot from their contents. Negative,
blocked and ambiguous outcomes retain the adapter's distinct semantics;
Gravatar absence is not proof of account absence.

No public HTTP/SSE endpoint, website chatbot, production dependency change,
authentication bypass, logging of targets, or scan-result persistence is added.

## Commands to run later

Run these PowerShell commands yourself from the MyRecon project root after
review. They create an isolated environment and install dependencies; **they
have not been run**. Python 3.12 is a suitable choice consistent with MyRecon's
runtime declaration; Python >=3.10 is required by the reference package.

```powershell
py -3.12 -m venv tools/user-scanner-mcp/.venv
./tools/user-scanner-mcp/.venv/Scripts/python.exe -m pip install -r tools/user-scanner-mcp/requirements.txt
./tools/user-scanner-mcp/.venv/Scripts/python.exe -I -B tools/user-scanner-mcp/launcher.py
```

The last command starts stdio and waits for an MCP client; it is not a scan CLI.
Usually the assistant client starts it instead. Review the example configuration
at `tools/user-scanner-mcp/client.example.json` and import/copy it only when you
choose to connect. It contains no secrets. All executable/script paths are
project-relative, and **the client must launch with MyRecon root as its working
directory**. Relative command/cwd support varies by client; configure its
documented working-directory option or launch the client from the project root.
Do not assume this JSON is accepted unchanged by every assistant. Never register
the unrestricted upstream `user-scanner-mcp` command instead.

Start by calling `list_available_modules` with `{}` to inspect local gates.
Scan shapes, for a later authorized integration, are
`{"username":"example-handle","module":"username.github"}` and
`{"email":"example@example.com","module":"email.gravatar"}`; both currently
return skipped. Add `"detail":true` only when bounded profile fields are needed.
Successful installation or tool discovery would still not establish live scan
correctness, ownership, provider access or production authorization.
