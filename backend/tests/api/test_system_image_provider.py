from conftest import register_or_create_user

_PROVIDER_BODY = {
    "name": "Platform Doubao",
    "provider_type": "doubao_ark",
    "base_url": "https://ark.example.invalid",
    "api_key": "sk-platform-key",
    "supports_list_models": False,
    "default_model": "ep-platform",
    "is_default": True,
    "is_active": True,
}


def test_non_admin_cannot_create_system_provider(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "sys_na", "sys_na@test.local", "PassSysNA123!"
    )
    r = full_client.post(
        "/v1/admin/system-image-providers/",
        headers=headers,
        json=_PROVIDER_BODY,
    )
    assert r.status_code == 403


def test_admin_crud_system_provider_and_user_list_excludes(full_client, auth_headers):
    created = full_client.post(
        "/v1/admin/system-image-providers/",
        headers=auth_headers,
        json=_PROVIDER_BODY,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["is_system"] is True
    assert "api_key" not in body
    assert body["api_key_masked"]
    provider_id = body["id"]

    headers = register_or_create_user(
        full_client, auth_headers, "sys_u", "sys_u@test.local", "PassSysU123!"
    )
    listed = full_client.get("/v1/image-providers/", headers=headers)
    assert listed.status_code == 200
    ids = [p["id"] for p in listed.json()]
    assert provider_id not in ids

    summary = full_client.get("/v1/image-providers/system/summary", headers=headers)
    assert summary.status_code == 200
    s = summary.json()
    assert s["has_provider"] is True
    assert s["id"] == provider_id
    assert s["default_model"] == "ep-platform"
    assert "api_key" not in s
    assert "api_key_masked" not in s

    deleted = full_client.delete(
        f"/v1/admin/system-image-providers/{provider_id}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204
