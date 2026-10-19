# Result ownership choices

Website result cards offer Mine, Not mine, Unsure, and Not reviewed (clear).
Signed-in choices persist under the authenticated user's private
`web/match_choices/<uid>` database node through `/api/match-choices`.
Guests keep choices in local browser storage; they are not automatically copied
into an account. Signing out or switching accounts replaces the visible choices.

Choices are keyed by profile URL, not username. URL fragments are ignored;
path case and query parameters remain significant. The same URL in later searches,
saved report views, and Deep Search reuses the choice. Different profile URLs or
aliases need their own review. Changing a choice does not change provider evidence.

JSON and CSV website exports include `ownership_choice` with a `user_assertion`
basis. Copied reports and printed cards display the choice. Existing downloaded
reports cannot be changed retroactively. Server scan caches contain no user choices.

Username clusters remain unverified regardless of their retrieval quality score;
the website displays Shared username rather than a percentage identity match.

Deploy the backend endpoint and website assets together. This change does not
ship an Android UI. Verify persistence against the deployed account store after
deployment; local tests use the in-memory store and mocked browser endpoints.
