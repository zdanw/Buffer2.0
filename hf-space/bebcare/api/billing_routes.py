from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import stripe

from bebcare.billing.packs import get_credit_packs, is_billing_enabled
from bebcare.config.settings import settings
from bebcare.database import get_db
from bebcare.models.user import User
from bebcare.schemas.billing import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    CreditPackOut,
    CreditPacksResponse,
)
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.services.stripe_billing_service import (
    BillingError,
    create_checkout_session,
    fulfill_checkout_session,
    fulfill_subscription_invoice,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/credit-packs", response_model=CreditPacksResponse)
def list_credit_packs(
    current_user: User = Depends(get_current_active_user),
):
    packs = get_credit_packs()
    return CreditPacksResponse(
        enabled=is_billing_enabled(),
        packs=[
            CreditPackOut(price_id=p.price_id, credits=p.credits, label=p.label)
            for p in packs
        ],
    )


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
def start_checkout_session(
    body: CheckoutSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        row, url = create_checkout_session(
            db, user_id=current_user.user_id, price_id=body.price_id
        )
        db.commit()
    except BillingError as e:
        db.rollback()
        if e.code == "billing_disabled":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="billing_disabled",
            )
        if e.code == "unknown_price":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="unknown_price"
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.code)
    return CheckoutSessionResponse(url=url, session_id=row.id)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="webhook_not_configured",
        )
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_signature"
        )

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            fulfill_checkout_session(
                db,
                stripe_session_id=session["id"],
                metadata=dict(session.get("metadata") or {}),
            )
            db.commit()
        except BillingError as e:
            db.rollback()
            if e.code == "session_not_found":
                # Acknowledge unknown sessions so Stripe stops retrying forever
                # when local row was never created (e.g. manual Dashboard session).
                return {"received": True, "ignored": True}
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.code
            )
    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        meta: dict = {}
        sub_id = invoice.get("subscription")
        if isinstance(sub_id, dict):
            meta = dict(sub_id.get("metadata") or {})
            sub_id = sub_id.get("id")
        if (not meta.get("user_id")) and isinstance(sub_id, str) and sub_id:
            try:
                stripe.api_key = settings.stripe_secret_key
                sub = stripe.Subscription.retrieve(sub_id)
                meta = dict(getattr(sub, "metadata", None) or sub.get("metadata") or {})
            except Exception:
                meta = {}
        if not meta.get("user_id"):
            meta = {**meta, **dict(invoice.get("metadata") or {})}
        try:
            fulfill_subscription_invoice(
                db,
                invoice_id=invoice["id"],
                billing_reason=invoice.get("billing_reason"),
                metadata=meta,
            )
            db.commit()
        except BillingError as e:
            db.rollback()
            if e.code in ("missing_user", "invalid_credits"):
                return {"received": True, "ignored": True}
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.code
            )
    return {"received": True}
