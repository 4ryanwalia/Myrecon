# PayPal Extended Scan Pack

Prepared locally: one-time USD 3.99 for the existing pack (10 non-expiring
Extended credits, unlimited standard scans and Deep Search). Razorpay and
Buy Me a Coffee remain available when configured.

## Configure in Render and PayPal

1. Rotate the live secret exposed in the screenshot. Do not reuse it.
2. In the backend service's environment, set `PAYPAL_CLIENT_ID` and
   `PAYPAL_CLIENT_SECRET` from the same PayPal REST app. Never place the secret
   in frontend code, Git, or chat. No sandbox username/password is required.
3. Register `https://myrecon.onrender.com/api/billing/paypal/webhook` in that
   app (use the actual backend hostname if changed). Subscribe to
   `CHECKOUT.ORDER.APPROVED` and `PAYMENT.CAPTURE.COMPLETED`.
4. Set the resulting `PAYPAL_WEBHOOK_ID` on the backend. This is the webhook
   registration ID, not the app ID or a client secret.
5. Test with `PAYPAL_ENV=sandbox` and the existing local-only dev account
   mode. Public sales stay disabled in sandbox. The sandbox approval redirects
   to the canonical website; for a local end-to-end test, return to local
   pricing with `?paypal=return&token=<sandbox-order-id>` manually. Never enable
   the development account on a public server.
6. For production, use live app credentials, a live webhook registration and
   `PAYPAL_ENV=live`. Persistent Firebase account storage is required.

## Release checks

- Deploy frontend and backend together. Check `/api/plans` reports
  `paypal_payments.enabled: true` only after live configuration is complete.
- Complete an authorized purchase and verify the destination account gained
  exactly 10 credits. Retry confirmation and webhook delivery; credits must
  remain 10. Also test cancellation and closing the tab after approval.
- The webhook handles approval even if the buyer closes the tab, verifies its
  signature via PayPal, and independently retrieves the order before granting.
- Returns, query parameters, emails and screenshots cannot prove payment.
  A pending or failed capture does not grant access. The buyer can select
  **Check PayPal payment** after signing back into the original account.
- Refunds and chargebacks require operator handling; automatic revocation is
  outside this checkout integration. Review the provider record and scan usage
  before adjusting access. Pending purchases should be reconciled from PayPal
  if webhook retries are exhausted.

Server-only order records live under `/web/paypal_orders/<environment>/<order>`
with UID, random binding and grant status. PayPal customer emails/names are not
copied to MyRecon. The existing atomic entitlement/payment ledger prevents
double grants and remains safe across database retries.

References: [Orders create](https://developer.paypal.com/api/orders/v2/orders-create),
[Orders capture](https://developer.paypal.com/api/orders/v2/orders-capture),
[Webhook signature verification](https://developer.paypal.com/api/webhooks/v1/verify-webhook-signature).
