"""Cross-user resource isolation (RED until Task 6+ stamps owner and filters queries)."""

from conftest import register_or_create_user


def test_user_b_cannot_get_user_a_brand(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_a", "iso_a@test.local", "PassA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_b", "iso_b@test.local", "PassB123!")
    created = full_client.post("/v1/brands/", headers=headers_a, json={"name": "Alpha Kit"})
    assert created.status_code in (200, 201)
    brand_id = created.json()["brand_id"]
    listed_b = full_client.get("/v1/brands/", headers=headers_b)
    assert listed_b.status_code == 200
    listed_body = listed_b.json()
    rows = listed_body["data"] if isinstance(listed_body, dict) else listed_body
    ids = [x["brand_id"] for x in rows]
    assert brand_id not in ids
    got = full_client.get(f"/v1/brands/{brand_id}", headers=headers_b)
    assert got.status_code == 404
