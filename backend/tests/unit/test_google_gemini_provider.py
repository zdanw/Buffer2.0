from unittest.mock import MagicMock, patch

from bebcare.providers.google_gemini import GoogleGeminiImageProvider

IMAGE_RESPONSE = {
    "status": "completed",
    "steps": [
        {
            "type": "model_output",
            "content": [
                {"type": "image", "data": "QUJD", "mime_type": "image/png"},
            ],
        }
    ],
}


def _ok(payload):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    resp.text = ""
    return resp


def test_generate_uses_interactions_api_and_omits_openai_fields():
    provider = GoogleGeminiImageProvider(
        api_key="AIza-test",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-3.1-flash-image",
    )
    with patch(
        "bebcare.providers.google_gemini.requests.post",
        return_value=_ok(IMAGE_RESPONSE),
    ) as post:
        urls = provider.generate(
            prompt="a cat",
            negative_prompt="blurry, watermark",
            size="2560x1440",
            model="gemini-3-pro-image",
        )

    post.assert_called_once()
    url = post.call_args.args[0]
    headers = post.call_args.kwargs["headers"]
    body = post.call_args.kwargs["json"]

    assert url == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert headers["x-goog-api-key"] == "AIza-test"
    assert "Authorization" not in headers
    assert "negative_prompt" not in body
    assert "image" not in body
    assert "size" not in body
    assert body["model"] == "gemini-3-pro-image"
    text_parts = [p["text"] for p in body["input"] if p.get("type") == "text"]
    assert text_parts
    assert "a cat" in text_parts[0]
    assert "blurry" in text_parts[0]
    assert body["generation_config"]["image_config"]["aspect_ratio"] == "16:9"
    assert urls == ["data:image/png;base64,QUJD"]


def test_generate_sends_reference_as_input_image_part():
    provider = GoogleGeminiImageProvider(
        api_key="AIza-test",
        base_url="https://generativelanguage.googleapis.com/v1beta/interactions",
        default_model="gemini-3.1-flash-image",
    )
    with patch(
        "bebcare.providers.google_gemini.requests.post",
        return_value=_ok(IMAGE_RESPONSE),
    ) as post:
        provider.generate(
            prompt="edit this product",
            reference_images=["data:image/jpeg;base64,QQ=="],
        )

    body = post.call_args.kwargs["json"]
    image_parts = [p for p in body["input"] if p.get("type") == "image"]
    assert len(image_parts) == 1
    assert image_parts[0]["data"] == "QQ=="
    assert image_parts[0]["mime_type"] == "image/jpeg"


def test_list_models_parses_native_gemini_payload():
    provider = GoogleGeminiImageProvider(
        api_key="AIza-test",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        supports_list_models=True,
    )
    payload = {
        "models": [
            {"name": "models/gemini-3.7-flash"},
            {"name": "models/gemini-3-pro-image"},
            {"name": "models/gemini-3.1-flash-image"},
        ]
    }
    with patch(
        "bebcare.providers.google_gemini.requests.get",
        return_value=_ok(payload),
    ) as get:
        models = provider.list_models()

    assert get.call_args.args[0] == "https://generativelanguage.googleapis.com/v1beta/models"
    ids = [m["id"] for m in models]
    assert ids == ["gemini-3-pro-image", "gemini-3.1-flash-image"]
