from conftest import register_or_create_user


def test_create_user_gets_trial_on_me(client, auth_headers):
    created = client.post(
        "/v1/auth/users",
        headers=auth_headers,
        json={
            "username": "cred_trial",
            "email": "cred_trial@test.local",
            "password": "PassTrial123!",
            "is_admin": False,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["image_credits_remaining"] == 2

    login = client.post(
        "/v1/auth/login/",
        data={"username": "cred_trial", "password": "PassTrial123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["image_credits_remaining"] == 2
    assert "has_system_image_provider" in me.json()


def test_non_admin_cannot_grant(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "cred_na", "cred_na@test.local", "PassCredNA123!"
    )
    me = full_client.get("/v1/auth/me", headers=headers).json()
    r = full_client.post(
        f"/v1/auth/users/{me['user_id']}/credit-grants",
        headers=headers,
        json={"quantity": 10},
    )
    assert r.status_code == 403


def test_admin_grant_increases_remaining(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "cred_ag", "cred_ag@test.local", "PassCredAG123!"
    )
    me = full_client.get("/v1/auth/me", headers=headers).json()
    before = me["image_credits_remaining"]
    r = full_client.post(
        f"/v1/auth/users/{me['user_id']}/credit-grants",
        headers=auth_headers,
        json={"quantity": 20, "note": "pack"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["remaining"] == 20
    me2 = full_client.get("/v1/auth/me", headers=headers).json()
    assert me2["image_credits_remaining"] == before + 20
