"""Minimal API contract tests (auth + generate status)."""


def test_root_and_health(client):
    assert client.get("/").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_login_ok(admin_tokens):
    assert admin_tokens["token_type"] == "bearer"
    assert admin_tokens["access_token"]
    assert admin_tokens["refresh_token"]


def test_login_bad_password(client):
    resp = client.post(
        "/v1/auth/login/",
        data={"username": "admin", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_requires_bearer(client):
    assert client.get("/v1/auth/me").status_code == 401


def test_me_with_access_token(client, auth_headers):
    resp = client.get("/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
    assert resp.json()["is_admin"] is True


def test_refresh_ok(client, admin_tokens):
    resp = client.post(
        "/v1/auth/refresh/",
        json={"refresh_token": admin_tokens["refresh_token"]},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert "refresh_token" not in resp.json()


def test_refresh_rejects_access_token(client, admin_tokens):
    resp = client.post(
        "/v1/auth/refresh/",
        json={"refresh_token": admin_tokens["access_token"]},
    )
    assert resp.status_code == 401


def test_bearer_rejects_refresh_token(client, admin_tokens):
    headers = {"Authorization": f"Bearer {admin_tokens['refresh_token']}"}
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


def test_create_user_without_trailing_slash(client, auth_headers):
    resp = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={
            "username": "ci_user",
            "email": "ci_user@test.local",
            "password": "CiUserPass123!",
            "is_admin": False,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["username"] == "ci_user"


def test_generate_status_unknown_404(client, auth_headers):
    resp = client.get(
        "/v1/generate/status/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_generate_status_requires_auth(client):
    assert (
        client.get(
            "/v1/generate/status/00000000-0000-0000-0000-000000000000"
        ).status_code
        == 401
    )
