"""Product duplicate endpoint."""

from conftest import register_or_create_user


def _create_brand(client, headers, name: str) -> str:
    resp = client.post("/v1/brands/", headers=headers, json={"name": name})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["brand_id"]


def _create_product(client, headers, name: str, brand_id: str, **extra):
    payload = {
        "product_name": name,
        "category": "test",
        "brand_id": brand_id,
        "description": "Desc",
        "selling_points": ["fast", "quiet"],
        "brand_voice": "Playful",
        "use_brand_voice": True,
        "has_on_body_branding": False,
        **extra,
    }
    resp = client.post("/v1/products/", headers=headers, json=payload)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_duplicate_product_copies_attributes_and_dimensions(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "dup_user", "dup_user@test.local", "PassDup123!"
    )
    brand_id = _create_brand(full_client, headers, "Dup Brand")
    source = _create_product(full_client, headers, "Source SKU", brand_id)

    dim_resp = full_client.post(
        f"/v1/prompt-dimensions/products/{source['product_id']}/dimensions/",
        headers=headers,
        json={
            "dimension_type": "styles",
            "item_id": "dup_style_1",
            "name": "Cozy",
            "is_custom": True,
        },
    )
    assert dim_resp.status_code in (200, 201), dim_resp.text

    dup = full_client.post(
        f"/v1/products/{source['product_id']}/duplicate",
        headers=headers,
    )
    assert dup.status_code == 201, dup.text
    body = dup.json()
    assert body["product_id"] != source["product_id"]
    assert body["product_name"] == "Source SKU (copy)"
    assert body["category"] == source["category"]
    assert body["description"] == source["description"]
    assert body["selling_points"] == source["selling_points"]
    assert body["brand_voice"] == source["brand_voice"]
    assert body["use_brand_voice"] == source["use_brand_voice"]
    assert body["has_on_body_branding"] == source["has_on_body_branding"]
    assert body["brand_id"] == brand_id
    assert len(body["dimensions"]) == 1
    assert body["dimensions"][0]["name"] == "Cozy"
    assert body["dimensions"][0]["item_id"] == "dup_style_1"


def test_duplicate_product_name_collision(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "dup_coll", "dup_coll@test.local", "PassDupColl123!"
    )
    brand_id = _create_brand(full_client, headers, "Coll Brand")
    source = _create_product(full_client, headers, "Widget", brand_id)
    first = full_client.post(f"/v1/products/{source['product_id']}/duplicate", headers=headers)
    assert first.status_code == 201
    assert first.json()["product_name"] == "Widget (copy)"

    second = full_client.post(f"/v1/products/{source['product_id']}/duplicate", headers=headers)
    assert second.status_code == 201
    assert second.json()["product_name"] == "Widget (copy 2)"


def test_user_b_cannot_duplicate_user_a_product(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "dup_iso_a", "dup_iso_a@test.local", "PassDupA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "dup_iso_b", "dup_iso_b@test.local", "PassDupB123!"
    )
    brand_id = _create_brand(full_client, headers_a, "Iso Brand")
    source = _create_product(full_client, headers_a, "Secret", brand_id)
    resp = full_client.post(
        f"/v1/products/{source['product_id']}/duplicate",
        headers=headers_b,
    )
    assert resp.status_code == 404
