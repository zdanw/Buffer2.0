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


_PROVIDER_BODY = {
    "name": "My Doubao",
    "provider_type": "doubao_ark",
    "base_url": "https://ark.example.invalid",
    "api_key": "sk-test-not-a-real-key",
    "supports_list_models": False,
    "is_default": True,
}


def _create_image_provider(client, headers, **extra):
    body = dict(_PROVIDER_BODY)
    body.update(extra)
    return client.post("/v1/image-providers/", headers=headers, json=body)


def test_non_admin_can_create_image_provider(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "iso_ip_na", "iso_ip_na@test.local", "PassIPNA123!"
    )
    created = _create_image_provider(full_client, headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "My Doubao"
    assert body.get("is_system") is not True
    listed = full_client.get("/v1/image-providers/", headers=headers)
    assert listed.status_code == 200
    ids = [x["id"] for x in listed.json()]
    assert body["id"] in ids
    assert "system" not in ids


def test_user_b_cannot_get_or_delete_user_a_image_provider(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "iso_ipa", "iso_ipa@test.local", "PassIPA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_ipb", "iso_ipb@test.local", "PassIPB123!"
    )
    created = _create_image_provider(full_client, headers_a, name="A Provider")
    assert created.status_code == 201, created.text
    provider_id = created.json()["id"]

    listed_b = full_client.get("/v1/image-providers/", headers=headers_b)
    assert listed_b.status_code == 200
    ids = [x["id"] for x in listed_b.json()]
    assert provider_id not in ids
    assert "system" not in ids

    got = full_client.get(f"/v1/image-providers/{provider_id}/models", headers=headers_b)
    assert got.status_code == 404
    deleted = full_client.delete(f"/v1/image-providers/{provider_id}", headers=headers_b)
    assert deleted.status_code == 404
    still = full_client.get("/v1/image-providers/", headers=headers_a)
    assert provider_id in [x["id"] for x in still.json()]


def test_user_a_cannot_generate_with_user_b_image_provider(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "iso_gip_a", "iso_gip_a@test.local", "PassGIPA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_gip_b", "iso_gip_b@test.local", "PassGIPB123!"
    )
    created_b = _create_image_provider(full_client, headers_b, name="B Provider")
    assert created_b.status_code == 201, created_b.text
    provider_id_b = created_b.json()["id"]
    product_id = _create_product(full_client, headers_a, "A Gen With B Provider")
    resp = full_client.post(
        "/v1/generate/copywriting/",
        headers=headers_a,
        json={
            "product_id": product_id,
            "platform": "instagram",
            "image_provider_id": provider_id_b,
        },
    )
    assert resp.status_code == 404


def test_generate_image_without_provider_returns_400(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "iso_noprov", "iso_noprov@test.local", "PassNoProv123!"
    )
    product_id = _create_product(full_client, headers, "No Provider Product")
    resp = full_client.post(
        "/v1/generate/image/",
        headers=headers,
        json={"product_id": product_id, "platform": "instagram"},
    )
    # No BYOK: 400 (exhausted/no mode), or 402/503 if trial+platform path without system provider.
    assert resp.status_code in (400, 402, 503), resp.text
    detail = resp.json().get("detail") or ""
    assert any(k in detail for k in ("供应商", "额度", "平台", "API"))


def test_non_admin_can_create_buffer_account(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "iso_buf_na", "iso_buf_na@test.local", "PassBufNA123!"
    )
    with patch(
        "bebcare.api.buffer_account_routes._probe_token",
        return_value={"email": "buf@test.local", "id": "remote-1"},
    ):
        created = full_client.post(
            "/v1/buffer-accounts/",
            headers=headers,
            json={"name": "My Buffer", "api_token": "fake-token", "is_default": True},
        )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "My Buffer"
    listed = full_client.get("/v1/buffer-accounts/", headers=headers)
    assert listed.status_code == 200
    assert body["id"] in [x["id"] for x in listed.json()]


def test_user_b_cannot_get_or_delete_user_a_buffer_account(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "iso_bufa", "iso_bufa@test.local", "PassBufA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_bufb", "iso_bufb@test.local", "PassBufB123!"
    )
    with patch(
        "bebcare.api.buffer_account_routes._probe_token",
        return_value={"email": "a@test.local", "id": "remote-a"},
    ):
        created = full_client.post(
            "/v1/buffer-accounts/",
            headers=headers_a,
            json={"name": "A Buffer", "api_token": "fake-token-a"},
        )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]

    listed_b = full_client.get("/v1/buffer-accounts/", headers=headers_b)
    assert listed_b.status_code == 200
    assert account_id not in [x["id"] for x in listed_b.json()]

    deleted = full_client.delete(f"/v1/buffer-accounts/{account_id}", headers=headers_b)
    assert deleted.status_code == 404
    still = full_client.get("/v1/buffer-accounts/", headers=headers_a)
    assert account_id in [x["id"] for x in still.json()]


def test_publish_without_buffer_account_returns_400(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "iso_nobuf", "iso_nobuf@test.local", "PassNoBuf123!"
    )
    product_id = _create_product(full_client, headers, "No Buffer Product")
    resp = full_client.post(
        "/v1/publish/",
        headers=headers,
        json={"text": "hello", "product_id": product_id, "platforms": ["instagram"]},
    )
    assert resp.status_code == 400
    assert "BUFFER_API_TOKEN" not in (resp.json().get("detail") or "")


def test_admin_list_brands_excludes_user_b_brand(full_client, auth_headers):
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_adm_b", "iso_adm_b@test.local", "PassAdmB123!"
    )
    created = full_client.post("/v1/brands/", headers=headers_b, json={"name": "User B Brand"})
    assert created.status_code in (200, 201)
    brand_id_b = created.json()["brand_id"]
    listed_admin = full_client.get("/v1/brands/", headers=auth_headers)
    assert listed_admin.status_code == 200
    ids = [x["brand_id"] for x in _list_rows(listed_admin)]
    assert brand_id_b not in ids


def test_admin_post_auth_users_returns_201(full_client, auth_headers):
    resp = full_client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={
            "username": "iso_t10_user",
            "email": "iso_t10_user@test.local",
            "password": "PassT10User123!",
            "is_admin": False,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["username"] == "iso_t10_user"


def test_admin_still_has_seeded_prompt_catalog(full_client, auth_headers):
    listed = full_client.get("/v1/prompt-dimensions/", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["pagination"]["total"] > 0
    assert _list_rows(listed)


def test_user_b_does_not_list_admin_prompt_dimensions(full_client, auth_headers):
    listed_admin = full_client.get("/v1/prompt-dimensions/", headers=auth_headers)
    assert listed_admin.status_code == 200
    admin_ids = {x["dimension_id"] for x in _list_rows(listed_admin)}
    assert admin_ids
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_pd_list", "iso_pd_list@test.local", "PassPdList123!"
    )
    listed_b = full_client.get("/v1/prompt-dimensions/", headers=headers_b)
    assert listed_b.status_code == 200
    b_ids = {x["dimension_id"] for x in _list_rows(listed_b)}
    assert admin_ids.isdisjoint(b_ids)
    assert listed_b.json()["pagination"]["total"] == 0


def test_user_can_create_own_prompt_dimension_hidden_from_others(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "iso_pd_na", "iso_pd_na@test.local", "PassPdNA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_pd_nb", "iso_pd_nb@test.local", "PassPdNB123!"
    )
    created = full_client.post(
        "/v1/prompt-dimensions/",
        headers=headers_a,
        json={
            "product_type": "test",
            "dimension_type": "scenes",
            "name": "User A scene",
        },
    )
    assert created.status_code == 201, created.text
    dim_id = created.json()["dimension_id"]
    listed_b = full_client.get("/v1/prompt-dimensions/", headers=headers_b)
    assert listed_b.status_code == 200
    b_ids = {x["dimension_id"] for x in _list_rows(listed_b)}
    assert dim_id not in b_ids
    got_b = full_client.get(f"/v1/prompt-dimensions/{dim_id}", headers=headers_b)
    assert got_b.status_code == 404


def test_cannot_bind_product_dimension_on_other_users_product(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "iso_pdb_a", "iso_pdb_a@test.local", "PassPdBA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_pdb_b", "iso_pdb_b@test.local", "PassPdBB123!"
    )
    product_id_a = _create_product(full_client, headers_a, "A Dim Product")
    bound = full_client.post(
        f"/v1/prompt-dimensions/products/{product_id_a}/dimensions/",
        headers=headers_b,
        json={"dimension_type": "scenes", "item_id": "custom-scene", "name": "Stolen scene"},
    )
    assert bound.status_code == 404


def test_brand_owner_can_initialize_pack_other_user_gets_404(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "iso_pack_a", "iso_pack_a@test.local", "PassPackA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "iso_pack_b", "iso_pack_b@test.local", "PassPackB123!"
    )
    created = full_client.post("/v1/brands/", headers=headers_a, json={"name": "Pack Brand"})
    assert created.status_code in (200, 201)
    brand_id = created.json()["brand_id"]
    owner_resp = full_client.post(
        f"/v1/brands/{brand_id}/initialize-pack", headers=headers_a
    )
    assert owner_resp.status_code == 200, owner_resp.text
    assert owner_resp.json().get("created", 0) > 0
    listed_a = full_client.get("/v1/prompt-dimensions/", headers=headers_a)
    listed_b = full_client.get("/v1/prompt-dimensions/", headers=headers_b)
    assert listed_a.status_code == 200
    assert listed_b.status_code == 200
    a_ids = {x["dimension_id"] for x in _list_rows(listed_a)}
    b_ids = {x["dimension_id"] for x in _list_rows(listed_b)}
    assert a_ids
    assert a_ids.isdisjoint(b_ids)
    assert listed_b.json()["pagination"]["total"] == 0
    other_resp = full_client.post(
        f"/v1/brands/{brand_id}/initialize-pack", headers=headers_b
    )
    assert other_resp.status_code == 404
