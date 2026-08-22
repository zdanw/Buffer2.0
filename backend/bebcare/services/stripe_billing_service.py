"""Stripe Hosted Checkout: create session + fulfill webhook + cancel/refund."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import stripe
from sqlalchemy.orm import Session

from bebcare.billing.packs import find_pack, is_billing_enabled
from bebcare.config.settings import settings
from bebcare.models.image_credit import ImageCreditGrant
from bebcare.models.stripe_checkout import StripeCheckoutSession
from bebcare.models.stripe_subscription import StripeSubscription
from bebcare.models.user import User
from bebcare.services.credit_grant_service import (
    SOURCE_STRIPE,
    STATUS_ACTIVE,
    create_grant,
    revoke_grant,
)


class BillingError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


_ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})


def _stripe_api_key() -> None:
    stripe.api_key = settings.stripe_secret_key


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    return dict(obj)


def _ts_to_dt(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(ts))
    except (TypeError, ValueError, OSError):
        return None


def _price_id_from_subscription(sub: dict[str, Any]) -> Optional[str]:
    items = (sub.get("items") or {}).get("data") or []
    if not items:
        return None
    price = items[0].get("price") or {}
    if isinstance(price, str):
        return price
    return (price.get("id") or None) if isinstance(price, dict) else None


def get_or_create_stripe_customer(db: Session, *, user: User) -> str:
    """Return Stripe customer id for user, creating one if needed."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    existing = (
        db.query(StripeSubscription)
        .filter(StripeSubscription.user_id == user.user_id)
        .order_by(StripeSubscription.updated_at.desc())
        .first()
    )
    if existing and existing.stripe_customer_id:
        user.stripe_customer_id = existing.stripe_customer_id
        db.flush()
        return existing.stripe_customer_id

    _stripe_api_key()
    customer = stripe.Customer.create(
        email=user.email or None,
        name=user.username or None,
        metadata={"user_id": user.user_id},
    )
    user.stripe_customer_id = customer["id"]
    db.flush()
    return customer["id"]


def upsert_subscription_record(
    db: Session,
    *,
    user_id: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    status: str,
    cancel_at_period_end: bool = False,
    current_period_end: Optional[datetime] = None,
    price_id: Optional[str] = None,
) -> StripeSubscription:
    row = (
        db.query(StripeSubscription)
        .filter(
            StripeSubscription.stripe_subscription_id == stripe_subscription_id
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = StripeSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=status,
            cancel_at_period_end=bool(cancel_at_period_end),
            current_period_end=current_period_end,
            price_id=price_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.user_id = user_id
        row.stripe_customer_id = stripe_customer_id
        row.status = status
        row.cancel_at_period_end = bool(cancel_at_period_end)
        if current_period_end is not None:
            row.current_period_end = current_period_end
        if price_id:
            row.price_id = price_id
        row.updated_at = now
    db.flush()
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is not None and not user.stripe_customer_id:
        user.stripe_customer_id = stripe_customer_id
        db.flush()
    return row


def sync_subscription_from_stripe_object(
    db: Session, sub_obj: Any, *, user_id: Optional[str] = None
) -> Optional[StripeSubscription]:
    sub = _as_dict(sub_obj)
    sub_id = (sub.get("id") or "").strip()
    if not sub_id:
        return None
    meta = dict(sub.get("metadata") or {})
    uid = (user_id or meta.get("user_id") or "").strip()
    if not uid:
        existing = (
            db.query(StripeSubscription)
            .filter(StripeSubscription.stripe_subscription_id == sub_id)
            .first()
        )
        if existing:
            uid = existing.user_id
        else:
            return None
    customer = sub.get("customer")
    if isinstance(customer, dict):
        customer_id = (customer.get("id") or "").strip()
    else:
        customer_id = (customer or "").strip()
    if not customer_id:
        return None
    return upsert_subscription_record(
        db,
        user_id=uid,
        stripe_customer_id=customer_id,
        stripe_subscription_id=sub_id,
        status=str(sub.get("status") or "unknown"),
        cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
        current_period_end=_ts_to_dt(sub.get("current_period_end")),
        price_id=_price_id_from_subscription(sub),
    )


def get_active_subscription(
    db: Session, *, user_id: str
) -> Optional[StripeSubscription]:
    rows = (
        db.query(StripeSubscription)
        .filter(StripeSubscription.user_id == user_id)
        .order_by(StripeSubscription.updated_at.desc())
        .all()
    )
    for row in rows:
        if row.status in _ACTIVE_STATUSES:
            return row
    return rows[0] if rows else None


def subscription_status_payload(
    db: Session, *, user_id: str
) -> dict[str, Any]:
    row = get_active_subscription(db, user_id=user_id)
    if row is None:
        return {
            "has_subscription": False,
            "status": None,
            "cancel_at_period_end": False,
            "current_period_end": None,
            "stripe_subscription_id": None,
            "price_id": None,
        }
    return {
        "has_subscription": row.status in _ACTIVE_STATUSES,
        "status": row.status,
        "cancel_at_period_end": bool(row.cancel_at_period_end),
        "current_period_end": row.current_period_end,
        "stripe_subscription_id": row.stripe_subscription_id,
        "price_id": row.price_id,
    }


def cancel_subscription_at_period_end(
    db: Session, *, user_id: str
) -> StripeSubscription:
    row = get_active_subscription(db, user_id=user_id)
    if row is None or row.status not in _ACTIVE_STATUSES:
        raise BillingError("no_subscription")
    if row.cancel_at_period_end:
        return row
    _stripe_api_key()
    sub = stripe.Subscription.modify(
        row.stripe_subscription_id, cancel_at_period_end=True
    )
    synced = sync_subscription_from_stripe_object(db, sub, user_id=user_id)
    assert synced is not None
    return synced


def resume_subscription(db: Session, *, user_id: str) -> StripeSubscription:
    row = get_active_subscription(db, user_id=user_id)
    if row is None or row.status not in _ACTIVE_STATUSES:
        raise BillingError("no_subscription")
    if not row.cancel_at_period_end:
        return row
    _stripe_api_key()
    sub = stripe.Subscription.modify(
        row.stripe_subscription_id, cancel_at_period_end=False
    )
    synced = sync_subscription_from_stripe_object(db, sub, user_id=user_id)
    assert synced is not None
    return synced


def create_checkout_session(
    db: Session, *, user_id: str, price_id: str
) -> tuple[StripeCheckoutSession, str]:
    if not is_billing_enabled():
        raise BillingError("billing_disabled")
    pack = find_pack(price_id)
    if pack is None:
        raise BillingError("unknown_price")

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise BillingError("user_not_found")

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

    customer_id = get_or_create_stripe_customer(db, user=user)
    _stripe_api_key()
    base = settings.frontend_base_url.rstrip("/")
    meta = {
        "user_id": user_id,
        "local_session_id": local_id,
        "credits": str(pack.credits),
        "price_id": pack.price_id,
    }
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": pack.price_id, "quantity": 1}],
        success_url=f"{base}/studio?checkout=success",
        cancel_url=f"{base}/studio?checkout=cancel",
        client_reference_id=user_id,
        metadata=meta,
        subscription_data={
            "metadata": {
                "user_id": user_id,
                "credits": str(pack.credits),
                "price_id": pack.price_id,
            }
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
    session_obj: Optional[dict[str, Any]] = None,
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
        _maybe_sync_subscription_from_checkout(
            db, row=row, session_obj=session_obj, metadata=metadata
        )
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
        _maybe_sync_subscription_from_checkout(
            db, row=row, session_obj=session_obj, metadata=metadata
        )
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
    expiry_days = max(1, int(settings.image_credit_stripe_expiry_days))
    grant = create_grant(
        db,
        user_id=user_id,
        quantity=credits,
        source=SOURCE_STRIPE,
        note=f"stripe:{price_id}" if price_id else "stripe",
        external_ref=stripe_session_id,
        expires_at=datetime.utcnow() + timedelta(days=expiry_days),
    )
    row.status = "paid"
    row.grant_id = grant.id
    row.updated_at = datetime.utcnow()
    db.flush()
    _maybe_sync_subscription_from_checkout(
        db, row=row, session_obj=session_obj, metadata=metadata
    )
    return row


def _maybe_sync_subscription_from_checkout(
    db: Session,
    *,
    row: StripeCheckoutSession,
    session_obj: Optional[dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    sess = dict(session_obj or {})
    sub_id = sess.get("subscription")
    if isinstance(sub_id, dict):
        sub_id = sub_id.get("id")
    customer_id = sess.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    if not isinstance(sub_id, str) or not sub_id.strip():
        return
    user_id = (metadata.get("user_id") or row.user_id).strip()
    _stripe_api_key()
    try:
        sub = stripe.Subscription.retrieve(sub_id)
        sync_subscription_from_stripe_object(db, sub, user_id=user_id)
    except Exception:
        if isinstance(customer_id, str) and customer_id.strip():
            upsert_subscription_record(
                db,
                user_id=user_id,
                stripe_customer_id=customer_id.strip(),
                stripe_subscription_id=sub_id.strip(),
                status="active",
                price_id=(metadata.get("price_id") or row.price_id or None),
            )


def fulfill_subscription_invoice(
    db: Session,
    *,
    invoice_id: str,
    billing_reason: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    subscription_id: Optional[str] = None,
) -> Optional[ImageCreditGrant]:
    """Grant credits on recurring subscription invoices (not the create invoice)."""
    reason = (billing_reason or "").strip()
    if reason in ("", "subscription_create"):
        # First period is fulfilled via checkout.session.completed
        if subscription_id:
            _stripe_api_key()
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                sync_subscription_from_stripe_object(db, sub)
            except Exception:
                pass
        return None

    invoice_id = (invoice_id or "").strip()
    if not invoice_id:
        raise BillingError("invalid_invoice")

    existing = (
        db.query(ImageCreditGrant)
        .filter(
            ImageCreditGrant.source == SOURCE_STRIPE,
            ImageCreditGrant.external_ref == invoice_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    metadata = dict(metadata or {})
    user_id = (metadata.get("user_id") or "").strip()
    if not user_id:
        raise BillingError("missing_user")

    credits_raw = metadata.get("credits")
    if credits_raw is not None and str(credits_raw).strip() != "":
        credits = int(credits_raw)
    else:
        price_id = (metadata.get("price_id") or "").strip()
        pack = find_pack(price_id) if price_id else None
        credits = int(pack.credits) if pack else 0
    if credits < 1:
        raise BillingError("invalid_credits")

    price_id = (metadata.get("price_id") or "").strip()
    expiry_days = max(1, int(settings.image_credit_stripe_expiry_days))
    grant = create_grant(
        db,
        user_id=user_id,
        quantity=credits,
        source=SOURCE_STRIPE,
        note=f"stripe_sub:{price_id}" if price_id else "stripe_sub",
        external_ref=invoice_id,
        expires_at=datetime.utcnow() + timedelta(days=expiry_days),
    )
    if subscription_id:
        try:
            _stripe_api_key()
            sub = stripe.Subscription.retrieve(subscription_id)
            sync_subscription_from_stripe_object(db, sub, user_id=user_id)
        except Exception:
            pass
    return grant


def _invoice_refund_amount(invoice: dict[str, Any]) -> int:
    """Refunded cents for an invoice payment (from Charge / PaymentIntent)."""
    # Prefer expanded charge object
    charge = invoice.get("charge")
    if isinstance(charge, dict):
        return int(charge.get("amount_refunded") or 0)
    if isinstance(charge, str) and charge.strip():
        try:
            ch = _as_dict(stripe.Charge.retrieve(charge))
            return int(ch.get("amount_refunded") or 0)
        except Exception:
            pass

    payment_intent = invoice.get("payment_intent")
    pi_id = None
    if isinstance(payment_intent, dict):
        # Expanded PI: check latest_charge
        latest = payment_intent.get("latest_charge")
        if isinstance(latest, dict):
            return int(latest.get("amount_refunded") or 0)
        if isinstance(latest, str) and latest.strip():
            try:
                ch = _as_dict(stripe.Charge.retrieve(latest))
                return int(ch.get("amount_refunded") or 0)
            except Exception:
                pass
        pi_id = payment_intent.get("id")
    elif isinstance(payment_intent, str):
        pi_id = payment_intent

    if pi_id:
        try:
            pi = _as_dict(
                stripe.PaymentIntent.retrieve(pi_id, expand=["latest_charge"])
            )
            latest = pi.get("latest_charge")
            if isinstance(latest, dict):
                return int(latest.get("amount_refunded") or 0)
            if isinstance(latest, str) and latest.strip():
                ch = _as_dict(stripe.Charge.retrieve(latest))
                return int(ch.get("amount_refunded") or 0)
            # Sum refunds listed on PI if present
            amount = int(pi.get("amount") or 0)
            amount_received = int(pi.get("amount_received") or amount)
            # Fallback: if status is canceled after refund some APIs leave amount
            refunds = (pi.get("charges") or {}).get("data") or []
            total = 0
            for ch in refunds:
                total += int(_as_dict(ch).get("amount_refunded") or 0)
            if total:
                return total
            _ = amount_received  # silence unused if no refunds
        except Exception:
            pass

    # Last resort: invoice-level field (often missing / always 0)
    return int(invoice.get("amount_refunded") or 0)


def list_user_invoices(db: Session, *, user_id: str) -> list[dict[str, Any]]:
    user = db.query(User).filter(User.user_id == user_id).first()
    customer_id = (user.stripe_customer_id if user else None) or None
    if not customer_id:
        row = (
            db.query(StripeSubscription)
            .filter(StripeSubscription.user_id == user_id)
            .order_by(StripeSubscription.updated_at.desc())
            .first()
        )
        customer_id = row.stripe_customer_id if row else None
    if not customer_id:
        return []
    _stripe_api_key()
    invoices = stripe.Invoice.list(
        customer=customer_id,
        limit=30,
        expand=["data.charge", "data.payment_intent.latest_charge"],
    )
    data = getattr(invoices, "data", None) or list(invoices)
    out: list[dict[str, Any]] = []
    for inv in data:
        inv_d = _as_dict(inv)
        invoice_id = inv_d.get("id") or ""
        grant = _find_grant_for_invoice(db, user_id=user_id, invoice=inv_d)
        amount_paid = int(inv_d.get("amount_paid") or 0)
        amount_refunded = _invoice_refund_amount(inv_d)
        out.append(
            {
                "invoice_id": invoice_id,
                "status": inv_d.get("status"),
                "amount_paid": amount_paid,
                "amount_refunded": amount_refunded,
                "currency": inv_d.get("currency"),
                "created": _ts_to_dt(inv_d.get("created")),
                "hosted_invoice_url": inv_d.get("hosted_invoice_url"),
                "grant_id": grant.id if grant else None,
                "grant_remaining": int(grant.remaining) if grant else 0,
                "refundable": (
                    inv_d.get("status") == "paid"
                    and amount_paid > 0
                    and amount_refunded < amount_paid
                ),
            }
        )
    return out


def _find_grant_for_invoice(
    db: Session, *, user_id: str, invoice: dict[str, Any]
) -> Optional[ImageCreditGrant]:
    invoice_id = (invoice.get("id") or "").strip()
    if invoice_id:
        g = (
            db.query(ImageCreditGrant)
            .filter(
                ImageCreditGrant.user_id == user_id,
                ImageCreditGrant.source == SOURCE_STRIPE,
                ImageCreditGrant.external_ref == invoice_id,
            )
            .first()
        )
        if g:
            return g

    sub_id = invoice.get("subscription")
    if isinstance(sub_id, dict):
        sub_id = sub_id.get("id")
    if not isinstance(sub_id, str) or not sub_id:
        return None

    reason = (invoice.get("billing_reason") or "").strip()
    if reason != "subscription_create":
        return None

    _stripe_api_key()
    try:
        sessions = stripe.checkout.Session.list(subscription=sub_id, limit=5)
        data = getattr(sessions, "data", None) or list(sessions)
        for sess in data:
            sid = sess.get("id") if isinstance(sess, dict) else getattr(sess, "id", None)
            if not sid:
                continue
            g = (
                db.query(ImageCreditGrant)
                .filter(
                    ImageCreditGrant.user_id == user_id,
                    ImageCreditGrant.source == SOURCE_STRIPE,
                    ImageCreditGrant.external_ref == sid,
                )
                .first()
            )
            if g:
                return g
    except Exception:
        return None
    return None


def refund_invoice(
    db: Session,
    *,
    user_id: str,
    invoice_id: str,
    revoke_credits: bool = False,
) -> dict[str, Any]:
    invoice_id = (invoice_id or "").strip()
    if not invoice_id:
        raise BillingError("invalid_invoice")

    user = db.query(User).filter(User.user_id == user_id).first()
    owned_customers: set[str] = set()
    if user and user.stripe_customer_id:
        owned_customers.add(user.stripe_customer_id)
    for sub_row in (
        db.query(StripeSubscription)
        .filter(StripeSubscription.user_id == user_id)
        .all()
    ):
        owned_customers.add(sub_row.stripe_customer_id)
    if not owned_customers:
        raise BillingError("no_customer")

    _stripe_api_key()
    inv = _as_dict(
        stripe.Invoice.retrieve(
            invoice_id, expand=["charge", "payment_intent.latest_charge"]
        )
    )
    customer = inv.get("customer")
    if isinstance(customer, dict):
        customer = customer.get("id")
    if customer not in owned_customers:
        raise BillingError("invoice_not_owned")

    if inv.get("status") != "paid":
        raise BillingError("invoice_not_paid")

    amount_paid = int(inv.get("amount_paid") or 0)
    amount_refunded = _invoice_refund_amount(inv)
    if amount_paid <= 0 or amount_refunded >= amount_paid:
        raise BillingError("already_refunded")

    payment_intent = inv.get("payment_intent")
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id")
    charge = inv.get("charge")
    if isinstance(charge, dict):
        charge = charge.get("id")

    if payment_intent:
        refund = stripe.Refund.create(payment_intent=payment_intent)
    elif charge:
        refund = stripe.Refund.create(charge=charge)
    else:
        raise BillingError("no_charge")

    revoked_grant_id = None
    if revoke_credits:
        grant = _find_grant_for_invoice(db, user_id=user_id, invoice=inv)
        if grant is not None and grant.status == STATUS_ACTIVE and grant.remaining > 0:
            revoked = revoke_grant(db, grant.id)
            revoked_grant_id = revoked.id

    refund_d = _as_dict(refund)
    return {
        "refund_id": refund_d.get("id"),
        "status": refund_d.get("status"),
        "amount": refund_d.get("amount"),
        "currency": refund_d.get("currency"),
        "invoice_id": invoice_id,
        "revoked_grant_id": revoked_grant_id,
    }
