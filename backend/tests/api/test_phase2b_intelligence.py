"""Phase 2B API: client cannot bypass rollout; generate still works."""

from unittest.mock import patch

from conftest import register_or_create_user


def _create_product(client, headers, name="Intel API"):
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
    assert created.status_code in (200, 201), created.text
    return created.json()


def test_generate_ignores_client_intelligence_mode_when_off(full_client, auth_headers):
    from bebcare.config.settings import settings

    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "off"
    headers = register_or_create_user(
        full_client, auth_headers, "intel_off", "intel_off@test.local", "PassIntelOff123!"
    )
    product = _create_product(full_client, headers)
    try:
        with patch(
            "bebcare.services.asset_intelligence_adapter._platform_vision_complete"
        ) as vision:
            resp = full_client.post(
                "/v1/generate/reference-selection/",
                headers=headers,
                json={
                    "product_id": product["product_id"],
                    "reference_count": 1,
                    "asset_intelligence_mode": "all",
                },
            )
            assert resp.status_code in (200, 400)
            vision.assert_not_called()
    finally:
        settings.asset_intelligence_mode = original
