# Subscription validation — 12 November 2026

214 backend tests pass, including trial deadline boundaries, cancellation,
renewal resets, duplicates, failures, ownership and existing pack preservation.
These use mocked provider records and controlled clocks. A browser regression
also verifies re-consent when sign-in reveals that the free trial is already used.

All four live PayPal plans were fetched and validated against advertised prices,
frequencies and the zero-cost three-day trial. Sandbox plans and a monthly
subscription were created. The IN buyer encountered a generic checkout error;
a new US sandbox buyer reached USD 0.00 approval but returned to login after
approval. The API remained approval_pending, and no trial access was granted.

Razorpay's test key was regenerated with explicit user approval and a 24-hour
transition for the previous key. Live keys were unaffected. A test monthly
subscription was created with start_at exactly three days after creation.
The official subscription test card reached the mock bank. Success actions
repeatedly timed out; payment ultimately failed/cancelled and no access was
granted. MyRecon's cancel endpoint then successfully cancelled that test
subscription, confirmed as cancelled by the provider.

Fixes: recheck eligibility after sign-in and require re-consent when billing
terms change; resume the existing pending subscription on a same-plan retry;
expose the server-owned pending PayPal approval link; explain that unapproved
checkout has no recurring authorization instead of presenting a provider outage
when its cancel API rejects approval_pending. Changing a pending PayPal checkout
to a different plan still requires reconciliation/support.

Not verified: completed provider trial activation, a real three-day wait,
automatic debit, active-trial cancellation, provider renewal, or actual webhook
delivery into MyRecon. Accelerated local tests do not prove scheduled charges.
No live purchases or production account edits were performed. Buy Me a Coffee
provider code, price and purchased-credit model were unchanged. Credentials and
private test harness/state are stored outside the repository.

References: https://developer.paypal.com/subscriptions/trial-period/ and
https://github.com/razorpay/markdown-docs/blob/master/payments/payments/test-card-details.md
