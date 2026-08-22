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
    InvoiceListResponse,
    InvoiceOut,
    RefundCreate,
    RefundResponse,
    SubscriptionStatusResponse,
)
from bebcare.services.auth_dependency import (
    get_current_active_user,
    get_current_admin_user,
)
from bebcare.services.stripe_billing_service import (
    BillingError,
    cancel_subscription_at_period_end,
    create_checkout_session,
    fulfill_checkout_session,
    fulfill_subscription_invoice,
    list_user_invoices,
    refund_invoice,
    resume_subscription,
    subscription_status_payload,
    sync_subscription_from_stripe_object,
)

router = APIRouter(prefix="/billing", tags=["billing"])


def _billing_http_error(e: BillingError) -> HTTPException:
    code = e.code
    if code == "billing_disabled":
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="billing_disabled",
        )
    if code in (
        "unknown_price",
        "invalid_invoice",
        "invoice_not_paid",
        "already_refunded",
    ):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
    if code in ("no_subscription", "no_customer", "invoice_not_owned", "no_charge"):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=code)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)


@router.get("/credit-packs", response_model=CreditPacksResponse)
def list_credit_packs(
    current_user: User = Depends(get_current_active_user),
):
    packs = get_credit_packs()
    return CreditPacksResponse(
        enabled=is_billing_enabled(),
        packs=[
            CreditPackOut(
                price_id=p.price_id,
                credits=p.credits,
                label=p.label,
                price_display=p.price_display,
            )
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
        raise _billing_http_error(e)
    return CheckoutSessionResponse(url=url, session_id=row.id)


@router.get("/subscription", response_model=SubscriptionStatusResponse)
def get_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return SubscriptionStatusResponse(
        **subscription_status_payload(db, user_id=current_user.user_id)
    )


@router.post("/subscription/cancel", response_model=SubscriptionStatusResponse)
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        cancel_subscription_at_period_end(db, user_id=current_user.user_id)
        db.commit()
    except BillingError as e:
        db.rollback()
        raise _billing_http_error(e)
    return SubscriptionStatusResponse(
        **subscription_status_payload(db, user_id=current_user.user_id)
    )


@router.post("/subscription/resume", response_model=SubscriptionStatusResponse)
def resume_user_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        resume_subscription(db, user_id=current_user.user_id)
        db.commit()
    except BillingError as e:
        db.rollback()
        raise _billing_http_error(e)
    return SubscriptionStatusResponse(
        **subscription_status_payload(db, user_id=current_user.user_id)
    )


@router.get(
    "/users/{user_id}/invoices",
    response_model=InvoiceListResponse,
)
def admin_list_invoices(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        rows = list_user_invoices(db, user_id=user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="stripe_error"
        )
    return InvoiceListResponse(invoices=[InvoiceOut(**r) for r in rows])


@router.post(
    "/users/{user_id}/refunds",
    response_model=RefundResponse,
)
def admin_refund_invoice(
    user_id: str,
    body: RefundCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        result = refund_invoice(
            db,
            user_id=user_id,
            invoice_id=body.invoice_id,
            revoke_credits=body.revoke_credits,
        )
        db.commit()
    except BillingError as e:
        db.rollback()
        raise _billing_http_error(e)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="stripe_error"
        )
    return RefundResponse(**result)


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
                session_obj=dict(session),
            )
            db.commit()
        except BillingError as e:
            db.rollback()
            if e.code == "session_not_found":
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
                meta = dict(
                    getattr(sub, "metadata", None) or sub.get("metadata") or {}
                )
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
                subscription_id=sub_id if isinstance(sub_id, str) else None,
            )
            db.commit()
        except BillingError as e:
            db.rollback()
            if e.code in ("missing_user", "invalid_credits"):
                return {"received": True, "ignored": True}
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=e.code
            )
    elif event["type"] in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        sub = event["data"]["object"]
        try:
            sync_subscription_from_stripe_object(db, sub)
            db.commit()
        except Exception:
            db.rollback()
            return {"received": True, "ignored": True}
    return {"received": True}
