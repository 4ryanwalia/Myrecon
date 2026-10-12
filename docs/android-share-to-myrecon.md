# Share to MyRecon

Android ACTION_SEND accepts text/plain and image/* in MainActivity.

- A recognized Instagram, TikTok, or GitHub profile URL opens Username lookup and schedules the existing scan after a short edit/cancel window. Tracking query parameters and fragments are removed locally.
- Multiple shared URLs remain editable in Username lookup without an automatic scan. Supported-host posts/videos and known short links request a full profile URL. Other URLs retain the existing QR / Link draft flow.
- A plain username or @handle opens Username lookup with the handle filled in.
- A content URI image opens QR / Link with an image preview and Check shared image action. This uses the existing on-device QR decoder; it is not reverse image search.
- Plain handles, generic links and image shares remain drafts. Only an unambiguous supported profile URL automatically requests the existing username action, including its existing access/ad gate.
- New shares replace the current shared draft, including when MainActivity receives onNewIntent. A saved request ID prevents rotation from replacing edits with the original shared input.
- Unsupported text, actions, or image URI schemes are ignored; unsupported SEND payloads show a short explanation. No storage or camera permission is needed to receive an image with a sender-provided URI read grant.

## Validation

Targeted JVM test: `:app:testDebugUnitTest --tests com.aryan.myrecon.SharedInputTest`.

Device checks before release:
1. Share a browser URL, text containing @handle, and a gallery QR screenshot to MyRecon from a cold start.
2. Repeat with MyRecon open on another tab, History, or a previous result.
3. Edit the shared URL, rotate, and confirm the edit remains. Share the same original URL again and confirm it replaces the draft.
4. On a fresh install, complete onboarding and confirm the share is retained.
5. Confirm recognized profile shares auto-submit once, while handles, ambiguous text and generic links remain drafts. Check the image explicitly; try a non-QR image and a revoked/unreadable URI to verify the existing error UI.

Android sources are ignored by this checkout's Git configuration; preserve them explicitly when preparing a release. These changes require a new Android build and distribution.
