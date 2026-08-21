"""Stripe Hosted Checkout: create session + fulfill webhook."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

import stripe
from sqlalchemy.orm import Session

from bebcare.billing.packs import find_pack, is_billing_enabled
from bebcare.config.settings import settings
from bebcare.models.image_credit import ImageCreditGrant
from bebcare.models.stripe_checkout import StripeCheckoutSession
from bebcare.services.credit_grant_service import SOURCE_STRIPE, create_grant


class BillingError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


def create_checkout_session(
    db: Session, *, user_id: str, price_id: str
) -> tuple[StripeCheckoutSession, str]:
    if not is_billing_enabled():
        raise BillingError("billing_disabled")
    pack = find_pack(price_id)
    if pack is None:
        raise BillingError("unknown_price")

    local_id = str(uuid.uuid4())
    row = StripeCheckoutSession(
        id=local_id,
        user_id=user_id,
        price_id=pack.price_id,
        credits=pack.credits,
        status="pending",
    )
    db.add(row)
    db.flush()

    stripe.api_key = settings.stripe_secret_key
    base = settings.frontend_base_url.rstrip("/")
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": pack.price_id, "quantity": 1}],
        success_url=f"{base}/studio?checkout=success",
        cancel_url=f"{base}/studio?checkout=cancel",
        client_reference_id=user_id,
        metadata={
            "user_id": user_id,
            "local_session_id": local_id,
            "credits": str(pack.credits),
            "price_id": pack.price_id,
        },
    )
    row.stripe_session_id = session["id"]
    row.updated_at = datetime.utcnow()
    db.flush()
    return row, session["url"]


def fulfill_checkout_session(
    db: Session,
    *,
    stripe_session_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> StripeCheckoutSession:
    metadata = dict(metadata or {})
    row = (
        db.query(StripeCheckoutSession)
        .filter(StripeCheckoutSession.stripe_session_id == stripe_session_id)
        .first()
    )
    if row is None:
        local_id = (metadata.get("local_session_id") or "").strip()
        if local_id:
            row = (
                db.query(StripeCheckoutSession)
                .filter(StripeCheckoutSession.id == local_id)
                .first()
            )
            if row is not None and not row.stripe_session_id:
                row.stripe_session_id = stripe_session_id

    if row is None:
        raise BillingError("session_not_found")

    if row.status == "paid":
        return row

    existing = (
        db.query(ImageCreditGrant)
        .filter(
            ImageCreditGrant.source == SOURCE_STRIPE,
            ImageCreditGrant.external_ref == stripe_session_id,
        )
        .first()
    )
    if existing is not None:
        row.status = "paid"
        row.grant_id = existing.id
        row.updated_at = datetime.utcnow()
        db.flush()
        return row

    user_id = (metadata.get("user_id") or row.user_id).strip()
    credits_raw = metadata.get("credits")
    if credits_raw is not None and str(credits_raw).strip() != "":
        credits = int(credits_raw)
    else:
        credits = int(row.credits)
    if credits < 1:
        raise BillingError("invalid_credits")

    price_id = (metadata.get("price_id") or row.price_id or "").strip()
    grant = create_grant(
        db,
        user_id=user_id,
        quantity=credits,
        source=SOURCE_STRIPE,
        note=f"stripe:{price_id}" if price_id else "stripe",
        external_ref=stripe_session_id,
    )
    row.status = "paid"
    row.grant_id = grant.id
    row.updated_at = datetime.utcnow()
    db.flush()
    return row
