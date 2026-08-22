import uuid
from datetime import datetime, timedelta

import pytest

from bebcare.database import Base, SessionLocal, engine
from bebcare.models.user import User
from bebcare.models.image_credit import ImageCreditGrant
from bebcare.models.stripe_checkout import StripeCheckoutSession
from bebcare.services.stripe_billing_service import (
    BillingError,
    create_checkout_session,
    fulfill_checkout_session,
)
import bebcare.models  # noqa: F401


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


@pytest.fixture()
def user_id(db_session):
    uid = str(uuid.uuid4())
    db_session.add(
        User(
            user_id=uid,
            username=f"u_{uid[:8]}",
            email=f"{uid[:8]}@test.local",
            hashed_password="x",
            is_active=True,
            is_admin=False,
        )
    )
    db_session.flush()
    return uid


@pytest.fixture()
def enable_billing(monkeypatch):
    from bebcare.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(
        settings_mod.settings,
        "stripe_credit_packs",
        '[{"price_id":"price_a","credits":20,"label":"20"}]',
    )
    monkeypatch.setattr(
        settings_mod.settings, "frontend_base_url", "http://localhost:5174"
    )
    monkeypatch.setattr(settings_mod.settings, "image_credit_stripe_expiry_days", 30)


def test_create_checkout_session_persists_pending(
    db_session, user_id, enable_billing, monkeypatch
):
    import stripe

    captured = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.com/test",
        }

    monkeypatch.setattr(stripe.checkout.Session, "create", _create)

    def _customer_create(**kwargs):
        return {"id": "cus_test_1"}

    monkeypatch.setattr(stripe.Customer, "create", _customer_create)
    row, url = create_checkout_session(
        db_session, user_id=user_id, price_id="price_a"
    )
    assert url.startswith("https://")
    assert row.status == "pending"
    assert row.stripe_session_id == "cs_test_1"
    assert row.credits == 20
    assert captured.get("mode") == "subscription"
    assert captured.get("customer") == "cus_test_1"
    assert captured.get("subscription_data", {}).get("metadata", {}).get("credits") == "20"


def test_create_checkout_unknown_price(db_session, user_id, enable_billing):
    with pytest.raises(BillingError) as ei:
        create_checkout_session(db_session, user_id=user_id, price_id="price_nope")
    assert ei.value.code == "unknown_price"


def test_fulfill_is_idempotent(db_session, user_id, enable_billing):
    local_id = str(uuid.uuid4())
    db_session.add(
        StripeCheckoutSession(
            id=local_id,
            user_id=user_id,
            stripe_session_id="cs_test_1",
            price_id="price_a",
            credits=20,
            status="pending",
        )
    )
    db_session.flush()
    meta = {
        "user_id": user_id,
        "local_session_id": local_id,
        "credits": "20",
        "price_id": "price_a",
    }
    fulfill_checkout_session(
        db_session, stripe_session_id="cs_test_1", metadata=meta
    )
    fulfill_checkout_session(
        db_session, stripe_session_id="cs_test_1", metadata=meta
    )
    grants = (
        db_session.query(ImageCreditGrant)
        .filter(ImageCreditGrant.external_ref == "cs_test_1")
        .all()
    )
    assert len(grants) == 1
    assert grants[0].quantity == 20
    assert grants[0].expires_at is not None
    delta = grants[0].expires_at - datetime.utcnow()
    assert timedelta(days=29) < delta < timedelta(days=31)
    row = (
        db_session.query(StripeCheckoutSession)
        .filter(StripeCheckoutSession.stripe_session_id == "cs_test_1")
        .one()
    )
    assert row.status == "paid"
    assert row.grant_id == grants[0].id


def test_fulfill_subscription_invoice_skips_create_and_grants_cycle(
    db_session, user_id, enable_billing
):
    from bebcare.services.stripe_billing_service import fulfill_subscription_invoice

    assert (
        fulfill_subscription_invoice(
            db_session,
            invoice_id="in_create",
            billing_reason="subscription_create",
            metadata={"user_id": user_id, "credits": "20", "price_id": "price_a"},
        )
        is None
    )
    grant = fulfill_subscription_invoice(
        db_session,
        invoice_id="in_cycle_1",
        billing_reason="subscription_cycle",
        metadata={"user_id": user_id, "credits": "20", "price_id": "price_a"},
    )
    assert grant is not None
    assert grant.quantity == 20
    assert grant.external_ref == "in_cycle_1"
    again = fulfill_subscription_invoice(
        db_session,
        invoice_id="in_cycle_1",
        billing_reason="subscription_cycle",
        metadata={"user_id": user_id, "credits": "20", "price_id": "price_a"},
    )
    assert again.id == grant.id


def test_cancel_and_resume_subscription(db_session, user_id, enable_billing, monkeypatch):
    import stripe
    from bebcare.models.stripe_subscription import StripeSubscription
    from bebcare.services.stripe_billing_service import (
        cancel_subscription_at_period_end,
        resume_subscription,
        subscription_status_payload,
    )

    db_session.add(
        StripeSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_x",
            status="active",
            cancel_at_period_end=False,
            current_period_end=datetime.utcnow() + timedelta(days=10),
            price_id="price_a",
        )
    )
    db_session.flush()

    def _modify(sub_id, **kwargs):
        return {
            "id": sub_id,
            "customer": "cus_x",
            "status": "active",
            "cancel_at_period_end": bool(kwargs.get("cancel_at_period_end")),
            "current_period_end": int((datetime.utcnow() + timedelta(days=10)).timestamp()),
            "metadata": {"user_id": user_id},
            "items": {"data": [{"price": {"id": "price_a"}}]},
        }

    monkeypatch.setattr(stripe.Subscription, "modify", _modify)

    cancel_subscription_at_period_end(
        db_session, user_id=user_id, stripe_subscription_id="sub_x"
    )
    payload = subscription_status_payload(db_session, user_id=user_id)
    assert payload["has_subscription"] is True
    assert payload["cancel_at_period_end"] is True
    assert len(payload["subscriptions"]) == 1
    assert payload["subscriptions"][0]["stripe_subscription_id"] == "sub_x"

    resume_subscription(
        db_session, user_id=user_id, stripe_subscription_id="sub_x"
    )
    payload = subscription_status_payload(db_session, user_id=user_id)
    assert payload["cancel_at_period_end"] is False


def test_cancel_other_subscriptions_immediately(
    db_session, user_id, enable_billing, monkeypatch
):
    import stripe
    from bebcare.models.stripe_subscription import StripeSubscription
    from bebcare.services.stripe_billing_service import (
        cancel_other_subscriptions_immediately,
        subscription_status_payload,
    )

    db_session.add(
        StripeSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_old",
            status="active",
            cancel_at_period_end=False,
            current_period_end=datetime.utcnow() + timedelta(days=10),
            price_id="price_a",
        )
    )
    db_session.add(
        StripeSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_new",
            status="active",
            cancel_at_period_end=False,
            current_period_end=datetime.utcnow() + timedelta(days=30),
            price_id="price_b",
        )
    )
    db_session.flush()

    def _cancel(sub_id):
        return {
            "id": sub_id,
            "customer": "cus_x",
            "status": "canceled",
            "cancel_at_period_end": False,
            "current_period_end": int((datetime.utcnow() + timedelta(days=10)).timestamp()),
            "metadata": {"user_id": user_id},
            "items": {"data": [{"price": {"id": "price_a"}}]},
        }

    monkeypatch.setattr(stripe.Subscription, "cancel", _cancel)

    cancelled = cancel_other_subscriptions_immediately(
        db_session,
        user_id=user_id,
        keep_stripe_subscription_id="sub_new",
    )
    assert len(cancelled) == 1
    assert cancelled[0].stripe_subscription_id == "sub_old"
    assert cancelled[0].status == "canceled"

    payload = subscription_status_payload(db_session, user_id=user_id)
    assert payload["has_subscription"] is True
    assert len(payload["subscriptions"]) == 1
    assert payload["subscriptions"][0]["stripe_subscription_id"] == "sub_new"


def test_invoice_refund_amount_reads_charge(monkeypatch, enable_billing):
    from bebcare.services.stripe_billing_service import _invoice_refund_amount

    assert (
        _invoice_refund_amount(
            {"amount_paid": 999, "charge": {"amount_refunded": 999}}
        )
        == 999
    )
    assert _invoice_refund_amount({"amount_paid": 999, "amount_refunded": 0}) == 0
