from unittest.mock import MagicMock, patch

from bebcare.providers.doubao_ark import DoubaoArkImageProvider
from bebcare.providers.generate_request import GenerateImageRequest
from bebcare.providers.google_gemini import GoogleGeminiImageProvider
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest


def _req():
    return GenerateImageRequest(
        prompt="redraw product",
        size="1024x1024",
        model="test-model",
        annotate_roles=True,
        references=ReferenceManifest(
            items=[
                ManifestItem(
                    order=0,
                    role="primary_subject",
                    cdn_url="https://cdn.test/p.jpg",
                    image_type="product",
                    authority="preferred",
                ),
                ManifestItem(
                    order=1,
                    role="scene",
                    cdn_url="https://cdn.test/s.jpg",
                    image_type="scene",
                    authority="suitability",
                ),
            ]
        ),
    )


def test_gemini_parts_match_manifest_order():
    provider = GoogleGeminiImageProvider(
        api_key="AIza-test",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-3.1-flash-image",
    )
    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    ok.json.return_value = {
        "status": "completed",
        "steps": [{"type": "model_output", "content": [{"type": "image", "data": "QQ=="}]}],
    }
    ok.text = ""
    with patch("bebcare.providers.google_gemini.requests.post", return_value=ok) as post, patch(
        "bebcare.providers.google_gemini._reference_to_part",
        side_effect=lambda url: {"type": "image", "url": url},
    ):
        provider.generate(request=_req())
    body = post.call_args.kwargs["json"]
    text = next(p["text"] for p in body["input"] if p.get("type") == "text")
    assert text.index("Image 1") < text.index("Image 2")
    assert "primary subject" in text
    urls = [p["url"] for p in body["input"] if p.get("type") == "image"]
    assert urls == ["https://cdn.test/p.jpg", "https://cdn.test/s.jpg"]


def test_ark_image_array_matches_manifest_order():
    provider = DoubaoArkImageProvider(
        api_key="sk",
        base_url="https://ark.example/api/v3",
        default_model="ep-test",
    )
    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    ok.json.return_value = {"data": [{"url": "https://cdn.example/out.png"}]}
    ok.text = ""
    with patch("bebcare.providers.doubao_ark.requests.post", return_value=ok) as post:
        provider.generate(request=_req())
    body = post.call_args.kwargs["json"]
    assert body["image"] == ["https://cdn.test/p.jpg", "https://cdn.test/s.jpg"]
    assert body["prompt"].index("Image 1") < body["prompt"].index("Image 2")
    assert "image2" not in body
