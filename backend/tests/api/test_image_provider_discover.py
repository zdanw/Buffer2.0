"""Tests for POST /image-providers/discover."""

from unittest.mock import patch


def test_discover_requires_auth(full_client):
    res = full_client.post(
        "/v1/image-providers/discover",
        json={
            "provider_type": "openai_compatible",
            "api_key": "sk-test",
        },
    )
    assert res.status_code == 401


def test_discover_returns_models(full_client, auth_headers):
    headers = auth_headers
    fake_models = [{"id": "gpt-image-1", "owned_by": "openai"}]
    with patch(
        "bebcare.api.image_provider_routes.discover_models_for_credentials",
        return_value=(True, fake_models, None),
    ):
        res = full_client.post(
            "/v1/image-providers/discover",
            headers=headers,
            json={
                "provider_type": "openai_compatible",
                "api_key": "sk-test-key-12345678",
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["models"][0]["id"] == "gpt-image-1"
    assert body["base_url"] == "https://api.openai.com/v1"
    assert body["supports_list_models"] is True


def test_discover_auth_failure(full_client, auth_headers):
    headers = auth_headers
    with patch(
        "bebcare.api.image_provider_routes.discover_models_for_credentials",
        return_value=(False, [], "Invalid API key"),
    ):
        res = full_client.post(
            "/v1/image-providers/discover",
            headers=headers,
            json={
                "provider_type": "doubao_ark",
                "api_key": "bad-key-12345678",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["models"] == []
    assert "Invalid" in (body["message"] or "")


def test_create_provider_without_base_url_uses_preset(full_client, auth_headers):
    headers = auth_headers
    res = full_client.post(
        "/v1/image-providers/",
        headers=headers,
        json={
            "name": "Preset URL Provider",
            "provider_type": "openai_compatible",
            "api_key": "sk-test-not-real",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["base_url"] == "https://api.openai.com/v1"
