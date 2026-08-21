import uuid

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


def test_create_checkout_session_persists_pending(
    db_session, user_id, enable_billing, monkeypatch
):
    import stripe

    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        lambda **kwargs: {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.com/test",
        },
    )
    row, url = create_checkout_session(
        db_session, user_id=user_id, price_id="price_a"
    )
    assert url.startswith("https://")
    assert row.status == "pending"
    assert row.stripe_session_id == "cs_test_1"
    assert row.credits == 20


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
    row = (
        db_session.query(StripeCheckoutSession)
        .filter(StripeCheckoutSession.stripe_session_id == "cs_test_1")
        .one()
    )
    assert row.status == "paid"
    assert row.grant_id == grants[0].id
