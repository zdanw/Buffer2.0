from bebcare.generator.content_generator import deepseek_chat_completions_url
from bebcare.services.auth_service import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from jose import jwt
from bebcare.config.settings import settings


def test_deepseek_url_appends_chat_completions():
    assert (
        deepseek_chat_completions_url("https://api.deepseek.com/v1")
        == "https://api.deepseek.com/v1/chat/completions"
    )
    full = "https://api.deepseek.com/v1/chat/completions"
    assert deepseek_chat_completions_url(full) == full
    assert (
        deepseek_chat_completions_url("https://api.deepseek.com/v1/")
        == "https://api.deepseek.com/v1/chat/completions"
    )


def test_password_roundtrip_and_compare():
    hashed = hash_password("SecretPass!")
    assert verify_password("SecretPass!", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_type_claims():
    access = create_access_token({"sub": "admin", "user_id": "1"})
    refresh = create_refresh_token({"sub": "admin", "user_id": "1"})
    access_payload = jwt.decode(
        access, settings.secret_key, algorithms=[settings.algorithm]
    )
    refresh_payload = jwt.decode(
        refresh, settings.secret_key, algorithms=[settings.algorithm]
    )
    assert access_payload["type"] == TOKEN_TYPE_ACCESS
    assert refresh_payload["type"] == TOKEN_TYPE_REFRESH
