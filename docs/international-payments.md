# Buy Me a Coffee international pack

Local integration prepared for the same Extended Scan Pack as the INR 99 checkout:
USD 3.99 once, 10 Extended credits, unlimited standard scans and Deep Search.
Razorpay remains the INR payment option. International checkout stays disabled
until the Shop URL, item ID, signing secret and persistent Firebase store are set.

## Shop configuration

1. Create a Shop item named **MyRecon Extended Scan Pack**, priced **USD 3.99**.
   Confirm that the published checkout accepts the exact decimal price before
   enabling it. Use Shop rather than the standard coffee donation button.
2. Description: "One-time access to Deep Search, unlimited standard username
   scans and 10 Extended scans across 3,000+ platforms. Credits never expire.
   Sign in at myrecon.xyz/pricing.html before buying, copy your activation code,
   and paste it into the required checkout question."
3. Add exactly one required question: **MyRecon activation code**. Disable
   quantity selection, member discounts and discounts that reduce payment below
   USD 3.99. This integration accepts one pack per order.
4. Confirmation: "Return to the MyRecon pricing page and refresh your account.
   Activation follows payment confirmation. If the pack is missing after an hour,
   email aryan@bugsnaps.in with your receipt and signed-in account email."
5. Set the post-purchase redirect to `https://www.myrecon.xyz/pricing.html#account`.

## Backend configuration

In Render, set `BUYMEACOFFEE_SHOP_URL` to the published
`https://buymeacoffee.com/<creator>/e/<numeric-id>` link and set
`BUYMEACOFFEE_ITEM_ID` to the same numeric ID.

Create an integration webhook to the backend's
`/api/billing/buymeacoffee/webhook` endpoint. Select `extra_purchase.created`
and `extra_purchase.updated`. Put its signing secret in
`BUYMEACOFFEE_WEBHOOK_SECRET` in Render; never commit or send it in chat.

## Verification before enabling sales

- Deploy backend and frontend and confirm `/api/plans` reports
  `international_payments.enabled: true`.
- Send a dashboard test event. It must be acknowledged without granting credits.
- Verify the live item costs exactly USD 3.99 and requires the activation code.
- Complete an authorized real purchase to a test account and verify 10 credits,
  unlimited standard scans and Deep Search. A redirect alone is not evidence.
- Retry the same signed event and confirm no additional credits are issued.
- Missing/incorrect codes are not activated automatically. Resolve those from
  the creator's verified order record and the customer's authenticated account.
  Refunds and chargebacks need operator handling; this integration does not
  automatically revoke entitlements. Never use screenshots as payment proof.

## Data and contracts

Signed-in checkout issues a random code stored only as a hash under
`/web/bmc_checkouts`, alongside UID, creation and expiry times. Paid purchases
are permanently bound to one UID under `/web/bmc_purchases`; paid credits use
the existing atomic grant and payment ledger. These server-only paths remain
under the existing `/web` client-deny rules. Codes are accepted only for purchases
made during their seven-day validity; delayed webhook retries remain valid.
Customer names/emails from Buy Me a Coffee payloads are not copied to MyRecon.
Only successful, live, unrefunded USD Shop purchases for the configured item
are considered. Donations and unrelated products do not grant access.

Sources:
- https://help.buymeacoffee.com/en/articles/9905719-a-complete-guide-on-buy-me-a-coffee-shop
- https://help.buymeacoffee.com/en/articles/15743173-how-to-setup-and-use-buy-me-a-coffee-webhooks
- https://cdn.buymeacoffee.com/assets/integrations/bmc-webhooks-openapi.json
