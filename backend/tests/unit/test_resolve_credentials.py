"""Credential resolution is per-owner; no env / platform-key fallback."""

from unittest.mock import MagicMock, patch

import pytest

from bebcare.providers.registry import resolve_image_provider
from bebcare.services.buffer_account_service import resolve_buffer_api_token


def test_resolve_image_provider_requires_owner_user_id():
    with pytest.raises(ValueError):
        resolve_image_provider(MagicMock(), owner_user_id=None)


def test_resolve_image_provider_system_id_is_not_found():
    with pytest.raises(ValueError):
        resolve_image_provider(
            MagicMock(), image_provider_id="system", owner_user_id="u-1"
        )


def test_resolve_image_provider_no_config_raises_without_env_fallback():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with patch("bebcare.providers.registry._env_fallback_provider") as env_fb:
        env_fb.side_effect = AssertionError("must not fall back to env Doubao")
        with pytest.raises(ValueError, match="设置"):
            resolve_image_provider(db, owner_user_id="u-1")


def test_resolve_buffer_token_no_account_returns_none_not_env():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    token = resolve_buffer_api_token(db, owner_user_id="u-1")
    assert token is None


def test_resolve_buffer_token_ignores_other_owner_default():
    other_default = MagicMock()
    other_default.owner_user_id = "u-b"
    other_default.is_active = True
    other_default.is_default = True
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    token = resolve_buffer_api_token(db, owner_user_id="u-a")
    assert token is None
