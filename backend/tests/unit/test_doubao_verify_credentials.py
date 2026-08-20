from unittest.mock import MagicMock, patch

import pytest
import requests

from bebcare.providers.doubao_ark import DoubaoArkImageProvider


def _provider():
    return DoubaoArkImageProvider(
        api_key="bad-key",
        base_url="https://ark.cn-beijing.volces.com/api/v3/images/generations",
        default_model="ep-test",
        supports_list_models=False,
    )


def test_verify_credentials_hits_models_endpoint_and_passes():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = ""
    with patch("bebcare.providers.doubao_ark.requests.get", return_value=resp) as get:
        _provider().verify_credentials()

    get.assert_called_once()
    assert get.call_args.args[0] == "https://ark.cn-beijing.volces.com/api/v3/models"
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer bad-key"


def test_verify_credentials_raises_on_auth_error():
    resp = MagicMock()
    resp.text = '{"error":{"code":"AuthenticationError","message":"The API key format is incorrect."}}'
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("401")
    with patch("bebcare.providers.doubao_ark.requests.get", return_value=resp):
        with pytest.raises(Exception, match="API key format is incorrect"):
            _provider().verify_credentials()
