# Multi-subscription UI + switch cancels old (immediate)

## Goal

When a user has multiple Stripe subscriptions, the buy-credits modal lists each one with its pack label and a per-subscription cancel/resume action. Buying a new pack and completing payment immediately cancels other active subscriptions (no refund); current-period credits remain until grant expiry.

## Backend

- `GET /billing/subscription` returns `subscriptions[]` (id, price_id, label, status, cancel_at_period_end, current_period_end) plus summary fields for compatibility.
- `POST /billing/subscription/cancel` and `/resume` require `stripe_subscription_id` (must belong to current user).
- Manual cancel remains **at period end** (`cancel_at_period_end=true`).
- On successful checkout fulfill: for every other active/trialing/past_due subscription of that user, **immediately cancel** via Stripe (no refund / no proration). Sync local rows. Do not revoke credit grants.

## Frontend

- Render one row per subscription: pack label, renewal/cancel status, cancel or resume.
- Confirm dialog includes pack label.
- Extra policy bullet: switching packs cancels the old subscription immediately; current credits kept; fee not refunded; billing follows the new pack.

## Out of scope

- Block repurchase while subscribed
- Stripe Customer Portal
- Automatic refunds / proration
