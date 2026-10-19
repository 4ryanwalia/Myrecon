# Linked profiles in website Deep Search

The website consumes the backend profile-discovery contract from
`modules/profile_connections.py`. Every streamed report may contain
`connections` and `connection_trail`. Connection rows contain `source`,
`destination`, `evidence_type`, `explanation`, `verification`, `can_follow`
and an account-bound `action`.

The explicit **Check this handle** button accepts only a POST action for
`/api/investigate/stream`, with `requires_user_action: true` and a bounded
`body.follow_token`. It sends only that token with the existing authentication
headers. It never sends a backend-supplied endpoint to fetch. Existing paid
access, backend admission, token expiry, cycle prevention and follow limits
still apply. A normal typed query continues to send `{ query }`.

Rows distinguish shared handles, explicit profile links and platform evidence.
The stronger verification label requires the accompanying Mastodon verification
timestamp or successful Keybase proof state and proof URL. MyRecon does not
independently revalidate Keybase signatures. Account existence is displayed
separately: a destination is confirmed only when its URL matches an account
returned in the current report's public activity list; otherwise it remains
unverified. Neither a found account nor a connection establishes common identity.

Suggestions appear while results stream, with follow controls disabled until
completion. Cancel aborts the existing request. Failed or cancelled follow
checks restore the source report, retaining evidence and allowing a retry.
Reports missing the discovery contract show an unavailable state and retain
the existing source sections. Empty results distinguish unavailable sources.
Account changes clear displayed evidence and downloads.

JSON retains the full report plus separate connection labels and existence
evidence. CSV includes report metadata, existing result groups, connections,
followed source edges and verification details. Both omit signed action tokens.
CSV quotes cells and neutralizes leading spreadsheet formula markers. Rendered
metadata is escaped and links must pass HTTP(S), credential, port and local-host
checks. The interface reuses existing panels, buttons, hints and details styling.

Implementation location: the user's Desktop MyRecon checkout. Backend discovery
changes were inspected read-only in the separate `4c46` MyRecon worktree; they
must be integrated alongside this frontend for discovery to become available.
The User Scanner reference was read only. No tests, builds, live scans,
deployments or dependency installs were run for this frontend change.
