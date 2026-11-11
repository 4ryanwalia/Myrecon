# Basic subscriptions

Prices: USD 3.99 monthly, USD 19.99 yearly, INR 299 monthly (Razorpay).
New subscribers receive one three-day trial across providers, with 3 Extended
scans. Paid monthly periods reset to 10 Extended scans; yearly periods reset
to 120. Unlimited standard scans and Deep Search last through confirmed access.
Subscription credits do not roll over. Existing packs retain their entitlements.
Buy Me a Coffee remains USD 3.99 one-time with 10 non-expiring credits.

Provider plans are public IDs in backend/core/billing_catalog.json, scoped to
a hash of the merchant API client ID. Environment BASIC_*_PLAN_ID overrides
are optional. Credentials and webhook secrets remain in the service environment.
Checkout verifies the provider plan amount and frequency before creating a
subscription. Production requires persistent account storage and live credentials.

PayPal app Subscriptions was enabled and live plans created on 12 November 2026.
Existing PayPal webhook includes subscription lifecycle and sale events.
Razorpay live plan plan_Tz2E3sFSVc4DU4 charges INR 299 every month;
its existing webhook now includes all subscription events (12 events total).
Razorpay subscriptions have a finite 120-charge schedule disclosed in terms.

Manage Basic refreshes provider state and cancels billing immediately while
retaining confirmed access until the trial/paid period ends. Signed provider
webhooks independently update access. Browser callbacks alone cannot grant it.
Creation timeouts retain a reservation to prevent duplicate billable contracts;
operators must reconcile such attempts against provider records before clearing
web/users/<uid>/subscription. Attempt bindings are under web/subscription_attempts.
Never delete a reservation until the provider confirms no live subscription.

Validation: mocked provider lifecycle, ownership, concurrency, period rollover,
expiry, cancellation, free-trial reuse and legacy-credit compatibility tests.
No customer purchase or real automatic renewal was performed during release.
