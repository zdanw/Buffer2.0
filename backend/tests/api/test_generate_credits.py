"""Platform credit gating on image generate endpoints."""

from unittest.mock import AsyncMock, patch

from conftest import register_or_create_user
from bebcare.database import SessionLocal
from bebcare.models.image_credit import ImageCreditGrant
from bebcare.models.user import User


def _create_product(client, headers, name):
    brand = client.post("/v1/brands/", headers=headers, json={"name": f"{name} Brand"})
    assert brand.status_code in (200, 201)
    created = client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": name,
            "category": "test",
            "brand_id": brand.json()["brand_id"],
        },
    )
    assert created.status_code in (200, 201)
    return created.json()["product_id"]


def _zero_credits_for_username(username: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        db.query(ImageCreditGrant).filter(ImageCreditGrant.user_id == user.user_id).delete()
        db.commit()
    finally:
        db.close()


def test_platform_generate_requires_credits(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "cred_z", "cred_z@test.local", "PassCredZ123!"
    )
    _zero_credits_for_username("cred_z")
    product_id = _create_product(full_client, headers, "Zero Credit Product")
    resp = full_client.post(
        "/v1/generate/image/",
        headers=headers,
        json={
            "product_id": product_id,
            "platform": "instagram",
            "image_provider_mode": "platform",
        },
    )
    assert resp.status_code == 402, resp.text


def test_copywriting_creates_no_reservation(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "cred_cw", "cred_cw@test.local", "PassCredCW123!"
    )
    product_id = _create_product(full_client, headers, "CW Product")
    before = SessionLocal()
    try:
        from bebcare.models.image_credit import ImageCreditReservation

        n0 = before.query(ImageCreditReservation).count()
    finally:
        before.close()

    with patch(
        "bebcare.api.generate_routes.ContentGenerator.generate_copywriting_async",
        new_callable=AsyncMock,
        return_value="hello",
    ):
        r = full_client.post(
            "/v1/generate/copywriting/",
            headers=headers,
            json={"product_id": product_id, "platform": "instagram"},
        )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        from bebcare.models.image_credit import ImageCreditReservation

        assert db.query(ImageCreditReservation).count() == n0
    finally:
        db.close()
