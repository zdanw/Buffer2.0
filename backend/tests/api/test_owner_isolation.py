"""Cross-user resource isolation (RED until Task 6+ stamps owner and filters queries)."""

from unittest.mock import AsyncMock, patch

from bebcare.models import BEBCARE_BRAND_ID, GENERIC_BRAND_ID
from conftest import register_or_create_user

_FAKE_PROVIDER_ID = "00000000-0000-0000-0000-000000000001"


def _list_rows(resp):
    body = resp.json()
    return body["data"] if isinstance(body, dict) else body


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


def _create_task(client, headers, name, **extra):
    payload = {
        "name": name,
        "cron": "0 9 * * *",
        "mode": "manual",
        "enabled": False,
        "platforms": ["instagram"],
    }
    payload.update(extra)
    return client.post("/v1/tasks/", headers=headers, json=payload)


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


def test_user_b_cannot_see_user_a_tasks(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_ta", "iso_ta@test.local", "PassTA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_tb", "iso_tb@test.local", "PassTB123!")
    created = _create_task(full_client, headers_a, "Task A")
    assert created.status_code in (200, 201)
    task_id = created.json()["task_id"]
    listed_b = full_client.get("/v1/tasks/", headers=headers_b)
    assert listed_b.status_code == 200
    ids = [str(x["task_id"]) for x in _list_rows(listed_b)]
    assert str(task_id) not in ids
    got = full_client.get(f"/v1/tasks/{task_id}", headers=headers_b)
    assert got.status_code == 404


def test_user_a_cannot_create_task_with_user_b_product(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_tpa", "iso_tpa@test.local", "PassTPA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_tpb", "iso_tpb@test.local", "PassTPB123!")
    product_id_b = _create_product(full_client, headers_b, "B Product")
    created = _create_task(
        full_client, headers_a, "Steal B product", target_products=[product_id_b]
    )
    assert created.status_code == 404


def test_task_create_rejects_unknown_image_provider(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "iso_tprv", "iso_tprv@test.local", "PassTPRV123!"
    )
    created = _create_task(
        full_client, headers, "Bad provider", image_provider_id=_FAKE_PROVIDER_ID
    )
    assert created.status_code == 404


def test_user_b_cannot_get_user_a_generate_status(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_ga", "iso_ga@test.local", "PassGA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_gb", "iso_gb@test.local", "PassGB123!")
    product_id = _create_product(full_client, headers_a, "Gen Product")
    with patch(
        "bebcare.api.generate_routes.ContentGenerator.generate_copywriting_async",
        new_callable=AsyncMock,
        return_value="copy",
    ):
        gen = full_client.post(
            "/v1/generate/copywriting/",
            headers=headers_a,
            json={"product_id": product_id, "platform": "instagram"},
        )
    assert gen.status_code in (200, 201)
    task_id = gen.json()["task_id"]
    owner_got = full_client.get(f"/v1/generate/status/{task_id}", headers=headers_a)
    assert owner_got.status_code == 200
    other_got = full_client.get(f"/v1/generate/status/{task_id}", headers=headers_b)
    assert other_got.status_code == 404


def test_generate_rejects_unknown_image_provider(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "iso_gprv", "iso_gprv@test.local", "PassGPRV123!"
    )
    product_id = _create_product(full_client, headers, "Gen Provider Product")
    resp = full_client.post(
        "/v1/generate/copywriting/",
        headers=headers,
        json={
            "product_id": product_id,
            "platform": "instagram",
            "image_provider_id": _FAKE_PROVIDER_ID,
        },
    )
    assert resp.status_code == 404


def test_generate_rejects_other_users_product(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_gpa", "iso_gpa@test.local", "PassGPA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_gpb", "iso_gpb@test.local", "PassGPB123!")
    product_id_b = _create_product(full_client, headers_b, "B Gen Product")
    resp = full_client.post(
        "/v1/generate/copywriting/",
        headers=headers_a,
        json={"product_id": product_id_b, "platform": "instagram"},
    )
    assert resp.status_code == 404


def test_user_b_cannot_see_user_a_drafts(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_da", "iso_da@test.local", "PassDA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_db", "iso_db@test.local", "PassDB123!")
    created = full_client.post(
        "/v1/tasks/drafts/",
        headers=headers_a,
        json={"copywritings": ["hello from A"]},
    )
    assert created.status_code in (200, 201)
    draft_id = created.json()["draft_id"]
    listed_b = full_client.get("/v1/tasks/drafts/", headers=headers_b)
    assert listed_b.status_code == 200
    ids = [str(x["draft_id"]) for x in _list_rows(listed_b)]
    assert str(draft_id) not in ids
    discarded = full_client.post(f"/v1/tasks/drafts/{draft_id}/discard/", headers=headers_b)
    assert discarded.status_code == 404
