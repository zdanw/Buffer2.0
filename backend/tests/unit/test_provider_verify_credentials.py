from unittest.mock import MagicMock, patch

import pytest
import requests

from bebcare.providers.aliyun_maas import AliyunMaasMultimodalProvider
from bebcare.providers.google_gemini import GoogleGeminiImageProvider
from bebcare.providers.openai_compatible import OpenAICompatibleImageProvider


def _http_error_resp(text: str = "Unauthorized"):
    resp = MagicMock()
    resp.text = text
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("401")
    return resp


def _ok_resp():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = ""
    return resp


def test_openai_verify_credentials_hits_models_and_raises_on_auth_error():
    provider = OpenAICompatibleImageProvider(
        api_key="sk-bad",
        base_url="https://api.openai.com/v1",
        default_model="dall-e-3",
    )
    with patch(
        "bebcare.providers.openai_compatible.requests.get",
        return_value=_http_error_resp('{"error":{"message":"Incorrect API key"}}'),
    ) as get:
        with pytest.raises(Exception, match="Incorrect API key"):
            provider.verify_credentials()
    assert get.call_args.args[0] == "https://api.openai.com/v1/models"
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer sk-bad"


def test_openai_verify_credentials_passes():
    provider = OpenAICompatibleImageProvider(
        api_key="sk-ok",
        base_url="https://api.openai.com/v1",
    )
    with patch(
        "bebcare.providers.openai_compatible.requests.get",
        return_value=_ok_resp(),
    ):
        provider.verify_credentials()


def test_openai_generate_omits_response_format_for_agnes():
    provider = OpenAICompatibleImageProvider(
        api_key="sk-agnes",
        base_url="https://api.agnes-ai.cn/v1",
        default_model="agnes-t2i-general-model",
        extra_params={"response_format": "url"},
    )
    ok = _ok_resp()
    ok.json.return_value = {"data": [{"url": "https://cdn.example/a.png"}]}
    with patch(
        "bebcare.providers.openai_compatible.requests.post",
        return_value=ok,
    ) as post:
        urls = provider.generate(prompt="a product shot", size="1024x1024")
    assert urls == ["https://cdn.example/a.png"]
    body = post.call_args.kwargs["json"]
    assert "response_format" not in body
    assert body["model"] == "agnes-t2i-general-model"


def test_openai_generate_allows_response_format_via_extra_params():
    provider = OpenAICompatibleImageProvider(
        api_key="sk-ok",
        base_url="https://api.openai.com/v1",
        default_model="dall-e-3",
        extra_params={"response_format": "url"},
    )
    ok = _ok_resp()
    ok.json.return_value = {"data": [{"url": "https://cdn.example/b.png"}]}
    with patch(
        "bebcare.providers.openai_compatible.requests.post",
        return_value=ok,
    ) as post:
        provider.generate(prompt="hi", size="1024x1024")
    assert post.call_args.kwargs["json"]["response_format"] == "url"


def test_aliyun_verify_credentials_hits_compatible_models():
    provider = AliyunMaasMultimodalProvider(
        api_key="sk-ali",
        base_url=(
            "https://ws-example.cn-beijing.maas.aliyuncs.com"
            "/api/v1/services/aigc/multimodal-generation/generation"
        ),
        default_model="qwen-image-edit",
    )
    with patch(
        "bebcare.providers.aliyun_maas.requests.get",
        return_value=_ok_resp(),
    ) as get:
        provider.verify_credentials()
    assert (
        get.call_args.args[0]
        == "https://ws-example.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/models"
    )


def test_aliyun_verify_credentials_raises_on_auth_error():
    provider = AliyunMaasMultimodalProvider(
        api_key="bad",
        base_url="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    )
    with patch(
        "bebcare.providers.aliyun_maas.requests.get",
        return_value=_http_error_resp("InvalidApiKey"),
    ):
        with pytest.raises(Exception, match="InvalidApiKey"):
            provider.verify_credentials()


def test_gemini_verify_credentials_hits_models_with_api_key_header():
    provider = GoogleGeminiImageProvider(
        api_key="AIza-bad",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-3.1-flash-image",
    )
    with patch(
        "bebcare.providers.google_gemini.requests.get",
        return_value=_http_error_resp("API key not valid"),
    ) as get:
        with pytest.raises(Exception, match="API key not valid"):
            provider.verify_credentials()
    assert (
        get.call_args.args[0]
        == "https://generativelanguage.googleapis.com/v1beta/models"
    )
    assert get.call_args.kwargs["headers"]["x-goog-api-key"] == "AIza-bad"


def test_gemini_verify_credentials_passes():
    provider = GoogleGeminiImageProvider(
        api_key="AIza-ok",
        base_url="https://generativelanguage.googleapis.com/v1beta",
    )
    with patch(
        "bebcare.providers.google_gemini.requests.get",
        return_value=_ok_resp(),
    ):
        provider.verify_credentials()
