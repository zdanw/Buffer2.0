from bebcare.models.stripe_checkout import StripeCheckoutSession
from bebcare.database import SessionLocal


def test_credit_packs_disabled_by_default(full_client, auth_headers, monkeypatch):
    from bebcare.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "stripe_secret_key", None)
    monkeypatch.setattr(settings_mod.settings, "stripe_credit_packs", "[]")
    r = full_client.get("/v1/billing/credit-packs", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["packs"] == []


def test_checkout_returns_503_when_disabled(full_client, auth_headers, monkeypatch):
    from bebcare.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "stripe_secret_key", None)
    r = full_client.post(
        "/v1/billing/checkout-session",
        headers=auth_headers,
        json={"price_id": "price_a"},
    )
    assert r.status_code == 503


def test_me_includes_billing_enabled(full_client, auth_headers, monkeypatch):
    from bebcare.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "stripe_secret_key", None)
    me = full_client.get("/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert "billing_enabled" in me.json()
    assert me.json()["billing_enabled"] is False


def test_webhook_fulfill_grants_credits(full_client, auth_headers, monkeypatch):
    from bebcare.config import settings as settings_mod
    import stripe

    monkeypatch.setattr(settings_mod.settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings_mod.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(
        settings_mod.settings,
        "stripe_credit_packs",
        '[{"price_id":"price_a","credits":20,"label":"20"}]',
    )

    me = full_client.get("/v1/auth/me", headers=auth_headers).json()
    user_id = me["user_id"]
    before = me["image_credits_remaining"]

    local_id = "local-sess-1"
    db = SessionLocal()
    try:
        db.add(
            StripeCheckoutSession(
                id=local_id,
                user_id=user_id,
                stripe_session_id="cs_test_wh",
                price_id="price_a",
                credits=20,
                status="pending",
            )
        )
        db.commit()
    finally:
        db.close()

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_wh",
                "metadata": {
                    "user_id": user_id,
                    "local_session_id": local_id,
                    "credits": "20",
                    "price_id": "price_a",
                },
            }
        },
    }

    def _construct(payload, sig, secret):
        assert secret == "whsec_test"
        return event

    monkeypatch.setattr(stripe.Webhook, "construct_event", _construct)

    r = full_client.post(
        "/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=x"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["received"] is True

    me2 = full_client.get("/v1/auth/me", headers=auth_headers).json()
    assert me2["image_credits_remaining"] == before + 20

    # idempotent
    r2 = full_client.post(
        "/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=x"},
    )
    assert r2.status_code == 200
    me3 = full_client.get("/v1/auth/me", headers=auth_headers).json()
    assert me3["image_credits_remaining"] == before + 20
