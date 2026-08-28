from unittest.mock import MagicMock, patch

from bebcare.providers.aliyun_maas import AliyunMaasMultimodalProvider
from bebcare.providers.doubao_ark import DoubaoArkImageProvider
from bebcare.providers.openai_compatible import OpenAICompatibleImageProvider
from bebcare.providers.image_model_filter import (
    filter_doubao_ark_models,
    filter_gemini_image_models,
    filter_openai_compatible_models,
    looks_like_image_model,
    openrouter_models_query,
)


def test_looks_like_image_model_ep_requires_metadata():
    assert not looks_like_image_model("ep-abc123")
    assert looks_like_image_model("ep-abc123", extra_text="doubao-seedream-3.0")


def test_openrouter_models_query():
    assert openrouter_models_query("https://openrouter.ai/api/v1") == {
        "output_modalities": "image"
    }
    assert openrouter_models_query("https://api.openai.com/v1") == {}


def test_filter_openai_compatible_uses_output_modalities():
    raw = [
        {"id": "gpt-4o", "output_modalities": ["text"]},
        {"id": "gpt-image-1", "output_modalities": ["image"]},
    ]
    out = filter_openai_compatible_models(raw)
    assert [m["id"] for m in out] == ["gpt-image-1"]


def test_filter_doubao_drops_ep_without_metadata():
    raw = [
        {"id": "ep-abc123"},
        {"id": "ep-def456", "model": "doubao-seedream-3.0", "name": "seedream"},
        {"id": "doubao-pro-32k"},
    ]
    out = filter_doubao_ark_models(raw)
    assert [m["id"] for m in out] == ["ep-def456"]


def test_filter_gemini_uses_name_and_metadata():
    raw = [
        {
            "name": "models/gemini-3.7-flash",
            "supportedGenerationMethods": ["generateContent"],
        },
        {
            "name": "models/gemini-3-pro-image",
            "supportedGenerationMethods": ["generateContent"],
        },
    ]
    out = filter_gemini_image_models(raw)
    assert [m["id"] for m in out] == ["gemini-3-pro-image"]


def test_openai_compatible_openrouter_passes_query_param():
    provider = OpenAICompatibleImageProvider(
        api_key="sk-test",
        base_url="https://openrouter.ai/api/v1",
        supports_list_models=True,
    )
    payload = {"data": [{"id": "flux-pro", "output_modalities": ["image"]}]}
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    with patch(
        "bebcare.providers.openai_compatible.requests.get",
        return_value=resp,
    ) as get:
        models = provider.list_models()
    assert get.call_args.kwargs["params"] == {"output_modalities": "image"}
    assert models[0]["id"] == "flux-pro"


def test_doubao_list_models_filters_endpoints():
    provider = DoubaoArkImageProvider(
        api_key="sk-test",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        supports_list_models=True,
    )
    payload = {
        "data": [
            {"id": "ep-chat", "model": "doubao-pro-32k"},
            {"id": "ep-img", "model": "doubao-seedream-3.0"},
        ]
    }
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    with patch("bebcare.providers.doubao_ark.requests.get", return_value=resp):
        models = provider.list_models()
    assert [m["id"] for m in models] == ["ep-img"]


def test_aliyun_list_models_uses_ig_catalog():
    provider = AliyunMaasMultimodalProvider(
        api_key="sk-test",
        base_url="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        supports_list_models=True,
    )
    payload = {
        "output": {
            "models": [
                {
                    "model_id": "qwen-image-edit-plus",
                    "inference_metadata": {"response_modality": ["Image"]},
                }
            ]
        }
    }
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    with patch(
        "bebcare.providers.aliyun_maas.requests.get",
        return_value=resp,
    ) as get:
        models = provider.list_models()
    assert get.call_args.args[0] == "https://dashscope.aliyuncs.com/api/v1/models"
    assert get.call_args.kwargs["params"] == {"capabilities": "IG"}
    assert models[0]["id"] == "qwen-image-edit-plus"
