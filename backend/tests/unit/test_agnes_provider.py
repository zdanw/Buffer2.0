from unittest.mock import MagicMock, patch

import pytest
import requests

from bebcare.providers.agnes import AgnesImageProvider


def _ok_resp(payload=None):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = ""
    resp.json.return_value = payload or {"data": [{"url": "https://cdn.example/a.png"}]}
    return resp


def test_agnes_generate_puts_refs_in_extra_body_and_omits_response_format():
    provider = AgnesImageProvider(
        api_key="sk-agnes",
        base_url="https://api.agnes-ai.cn/v1",
        default_model="agnes-image-2.1-flash",
        extra_params={"response_format": "url"},
    )
    with patch(
        "bebcare.providers.agnes.requests.post",
        return_value=_ok_resp(),
    ) as post:
        urls = provider.generate(
            prompt="merge product into scene",
            reference_images=[
                "https://cdn.example/bed.jpg",
                "https://cdn.example/product.jpg",
            ],
            size="1024x1024",
        )
    assert urls == ["https://cdn.example/a.png"]
    body = post.call_args.kwargs["json"]
    assert body["model"] == "agnes-image-2.1-flash"
    assert "response_format" not in body
    assert "image" not in body
    assert body["extra_body"]["image"] == [
        "https://cdn.example/bed.jpg",
        "https://cdn.example/product.jpg",
    ]
    assert post.call_args.args[0] == "https://api.agnes-ai.cn/v1/images/generations"


def test_agnes_generate_without_refs_omits_extra_body():
    provider = AgnesImageProvider(
        api_key="sk-agnes",
        base_url="https://api.agnes-ai.cn/v1",
    )
    with patch(
        "bebcare.providers.agnes.requests.post",
        return_value=_ok_resp(),
    ) as post:
        provider.generate(prompt="a crib", size="768x1024")
    body = post.call_args.kwargs["json"]
    assert "extra_body" not in body
    assert "image" not in body


def test_agnes_verify_credentials_hits_models():
    provider = AgnesImageProvider(
        api_key="sk-agnes",
        base_url="https://api.agnes-ai.cn/v1",
    )
    bad = MagicMock()
    bad.text = "Unauthorized"
    bad.raise_for_status.side_effect = requests.exceptions.HTTPError("401")
    with patch("bebcare.providers.agnes.requests.get", return_value=bad) as get:
        with pytest.raises(Exception, match="Unauthorized"):
            provider.verify_credentials()
    assert get.call_args.args[0] == "https://api.agnes-ai.cn/v1/models"


def test_registry_builds_agnes_provider():
    from bebcare.providers.registry import _build_provider

    config = MagicMock()
    config.provider_type = "agnes"
    config.base_url = "https://api.agnes-ai.cn/v1"
    config.default_model = "agnes-image-2.1-flash"
    config.extra_headers = {}
    config.extra_params = {}
    config.supports_list_models = True
    provider = _build_provider(config, "sk-test")
    from bebcare.providers.agnes import AgnesImageProvider as Cls

    assert isinstance(provider, Cls)
