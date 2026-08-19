"""Cross-user resource isolation (RED until Task 6+ stamps owner and filters queries)."""

from bebcare.models import BEBCARE_BRAND_ID, GENERIC_BRAND_ID
from conftest import register_or_create_user


def _list_rows(resp):
    body = resp.json()
    return body["data"] if isinstance(body, dict) else body


def test_user_b_cannot_get_user_a_brand(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_a", "iso_a@test.local", "PassA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_b", "iso_b@test.local", "PassB123!")
    created = full_client.post("/v1/brands/", headers=headers_a, json={"name": "Alpha Kit"})
    assert created.status_code in (200, 201)
    brand_id = created.json()["brand_id"]
    listed_b = full_client.get("/v1/brands/", headers=headers_b)
    assert listed_b.status_code == 200
    ids = [x["brand_id"] for x in _list_rows(listed_b)]
    assert brand_id not in ids
    got = full_client.get(f"/v1/brands/{brand_id}", headers=headers_b)
    assert got.status_code == 404


def test_regular_user_does_not_see_seeded_system_brands(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "iso_seed", "iso_seed@test.local", "PassSeed123!"
    )
    listed = full_client.get("/v1/brands/", headers=headers)
    assert listed.status_code == 200
    ids = [x["brand_id"] for x in _list_rows(listed)]
    assert GENERIC_BRAND_ID not in ids
    assert BEBCARE_BRAND_ID not in ids


def test_user_b_cannot_get_user_a_product(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_pa", "iso_pa@test.local", "PassPA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_pb", "iso_pb@test.local", "PassPB123!")
    brand = full_client.post("/v1/brands/", headers=headers_a, json={"name": "Prod Brand A"})
    assert brand.status_code in (200, 201)
    brand_id = brand.json()["brand_id"]
    created = full_client.post(
        "/v1/products/",
        headers=headers_a,
        json={"product_name": "P1", "category": "test", "brand_id": brand_id},
    )
    assert created.status_code in (200, 201)
    product_id = created.json()["product_id"]
    listed_b = full_client.get("/v1/products/", headers=headers_b)
    assert listed_b.status_code == 200
    ids = [x["product_id"] for x in _list_rows(listed_b)]
    assert product_id not in ids
    got = full_client.get(f"/v1/products/{product_id}", headers=headers_b)
    assert got.status_code == 404


def test_user_a_cannot_attach_product_to_user_b_brand(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_ba", "iso_ba@test.local", "PassBA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_bb", "iso_bb@test.local", "PassBB123!")
    brand_b = full_client.post("/v1/brands/", headers=headers_b, json={"name": "Brand B"})
    assert brand_b.status_code in (200, 201)
    brand_id_b = brand_b.json()["brand_id"]
    created = full_client.post(
        "/v1/products/",
        headers=headers_a,
        json={"product_name": "P1", "category": "test", "brand_id": brand_id_b},
    )
    assert created.status_code == 404
