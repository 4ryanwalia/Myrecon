# Deep Search linked profiles

`POST /api/investigate/stream` accepts the existing `{ "query": "@handle" }` request. Paid access, admission limits and NDJSON partial/complete/error events are unchanged. Both partial and complete result data now contain:

```json
{
  "connections": [{
    "source": {"platform": "GitHub", "handle": "first", "url": "https://github.com/first", "source": "GitHub public API"},
    "destination": {"platform": "Twitter / X", "handle": "second", "url": "https://x.com/second"},
    "evidence_type": "profile_link",
    "explanation": "An explicit account link was published in this profile's public metadata; ownership is not independently confirmed.",
    "verification": null,
    "can_follow": true,
    "action": {"method": "POST", "endpoint": "/api/investigate/stream", "body": {"follow_token": "server-signed-token"}, "requires_user_action": true}
  }],
  "connection_trail": [],
  "connection_limits": {"suggestions": 30, "follow_depth": 3}
}
```

Evidence types are separate: `same_username` connects returned profiles sharing the query handle, `profile_link` describes an explicit metadata link, and `platform_verified` requires Mastodon `verified_at` on a field containing one URL or a Keybase successful proof state and proof URL. Fields containing several URLs remain unverified because the timestamp does not identify a destination. A bio link or `verified: true` boolean alone never qualifies. Verification is provider-reported evidence, not MyRecon signature validation or a general identity conclusion.

The frontend sends the supplied action body only on an explicit Follow click, with its existing authentication headers. It runs the existing handle Deep Search service. The new search returns the signed, source-attributed `connection_trail` alongside its own results. It does not fetch arbitrary linked pages, sweep discovered emails, or automatically follow any further handle. Unsupported account routes produce no connection or follow action. Name candidates retain their candidate status.

Actions expire after one hour and are bound to the authenticated user. Tampered, expired, cyclic, private-network or unsupported destinations return the existing 422 validation error before starting providers. Authentication and paid-plan failures still return 401/402; admission failure returns 429. An action cannot be forged by posting a connection object. A shared configured `SECRET_KEY` is needed across backend workers for action signatures, as for existing signed application features.

Account recognition reverses MyRecon's existing standard and Extended URL templates, including subdomain and query formats, with explicit adapter aliases. It rejects post/repository paths, credentials, nonstandard ports and unsupported hosts. Destinations use the existing outbound public-network guard, rechecked on Follow. Up to 30 attributed connection rows are returned, deduplicated by source, destination and evidence type. Already visited accounts have no follow action. Trails stop after three explicit follows. Same-username rows do not offer redundant follows.

JSON exports include connections, verification and the complete source trail. Executable action tokens are omitted from frontend downloads. Existing `owner_links`, public activity and candidate fields remain available for compatibility.

The supplied user-scanner reference was inspected for metadata sources, particularly GitHub's public `social_accounts` endpoint. The implementation uses MyRecon's adapters and network guard; it does not import the reference engine or its email cross-scan behavior.
