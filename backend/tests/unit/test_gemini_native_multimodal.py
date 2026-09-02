"""Native Gemini BYOK analysis/QA transport. No live provider calls."""

import json

from bebcare.config.settings import settings
from bebcare.providers.image_model_filter import (
    filter_gemini_vision_models,
    gemini_model_accepts_image_input,
)
from bebcare.schemas.generate import GenerateRequest, ReferenceSelectionRequest
from bebcare.services.asset_intelligence_policy import AnalysisFailure
from bebcare.services.gemini_native_multimodal import (
    _generate_content_body,
    openai_messages_to_gemini,
    owner_gemini_intelligence_enabled,
    select_vision_model,
)


def _flash_item(name, methods):
    return {"name": f"models/{name}", "supportedGenerationMethods": methods}


def test_vision_filter_skips_image_generation_models():
    raw = [
        _flash_item("gemini-3.1-flash-image", ["generateContent"]),
        _flash_item("gemini-2.0-flash", ["generateContent", "countTokens"]),
        _flash_item("gemini-embedding-001", ["embedContent"]),
        {"name": "models/imagen-3.0", "supportedGenerationMethods": ["predict"]},
    ]
    vision = filter_gemini_vision_models(raw)
    ids = [row["id"] for row in vision]
    assert ids == ["gemini-2.0-flash"]
    assert gemini_model_accepts_image_input(raw[1]) is True
    assert gemini_model_accepts_image_input(raw[0]) is False


def test_select_vision_model_prefers_current_flash_not_image_or_stale():
    raw = [
        _flash_item("gemini-3.1-flash-image", ["generateContent"]),
        _flash_item("gemini-2.5-flash", ["generateContent"]),
        _flash_item("gemini-3.7-flash", ["generateContent"]),
    ]
    assert select_vision_model(raw) == "gemini-3.7-flash"


def test_pinned_image_model_rejected():
    raw = [_flash_item("gemini-2.0-flash", ["generateContent"])]
    try:
        select_vision_model(raw, pinned="gemini-3.1-flash-image")
        raise AssertionError("expected analysis_model_not_vision_capable")
    except AnalysisFailure as exc:
        assert exc.error_category == "analysis_model_not_vision_capable"


def test_native_payload_uses_interactions_image_parts_not_openai_chat():
    from bebcare.services.gemini_native_multimodal import _resize_bytes
    from PIL import Image
    from io import BytesIO

    buf = BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(buf, format="JPEG")
    mime, data = _resize_bytes(buf.getvalue(), max_side=32)
    url = f"data:{mime};base64,{data}"
    body = openai_messages_to_gemini(
        [
            {"role": "system", "content": "sys"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            },
        ]
    )
    parts = body["input"]
    assert any(part.get("type") == "text" and "sys" in part.get("text", "") for part in parts)
    assert any(part.get("type") == "image" and part.get("data") for part in parts)
    assert not any("image_url" in part or "inline_data" in part for part in parts)
    gc = _generate_content_body(parts, max_tokens=64)
    assert any("inline_data" in part for part in gc["contents"][0]["parts"])
    assert gc["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_response_schema_keeps_phase2b_enums():
    from bebcare.schemas.asset_intelligence import AssetIntelligenceResult
    from bebcare.services.gemini_native_multimodal import gemini_response_schema

    schema = gemini_response_schema(AssetIntelligenceResult.model_json_schema())
    assert "product" in schema["properties"]["asset_source_type"]["enum"]
    assert "$ref" not in json.dumps(schema)


def test_analysis_provider_name_follows_transport():
    from bebcare.services.asset_intelligence_adapter import analysis_provider_name
    from bebcare.services.gemini_native_multimodal import OWNER_GEMINI_PROVIDER

    original = settings.asset_intelligence_transport
    try:
        settings.asset_intelligence_transport = "platform"
        assert analysis_provider_name() == "platform_vision"
        settings.asset_intelligence_transport = "owner_gemini_byok"
        assert analysis_provider_name() == OWNER_GEMINI_PROVIDER
    finally:
        settings.asset_intelligence_transport = original


def test_coerce_intelligence_payload_maps_gemini_free_text():
    from bebcare.services.asset_intelligence_adapter import coerce_intelligence_payload

    out = coerce_intelligence_payload(
        {
            "asset_source_type": "user_photo",
            "subject_or_scene": "A baby monitor display parent unit on a table",
            "people_or_hands_presence": "reflection_only",
            "packaging_presence": "none",
            "generation_suitability": "usable_with_caveats",
            "dominant_offering_evidence": "Bebcare video baby monitor unit with display screen",
            "broad_composition": "wide_angle_tabletop",
            "broad_lighting": "indoor_ambient",
        }
    )
    assert out["asset_source_type"] == "product"
    assert out["subject_or_scene"] == "subject"
    assert out["people_or_hands_presence"] == "likely"
    assert out["packaging_presence"] == "absent"
    assert out["generation_suitability"] == "primary_subject"
    assert out["dominant_offering_evidence"] == "physical_product"
    assert out["broad_composition"] == "wide"
    assert out["broad_lighting"] == "other"


def test_byok_transport_is_env_only_and_off_by_default():
    original = settings.asset_intelligence_transport
    try:
        settings.asset_intelligence_transport = "platform"
        assert owner_gemini_intelligence_enabled() is False
        assert "asset_intelligence_transport" not in GenerateRequest.model_fields
        assert "visual_fidelity_qa_transport" not in GenerateRequest.model_fields
        assert "asset_intelligence_transport" not in ReferenceSelectionRequest.model_fields
        settings.asset_intelligence_transport = "owner_gemini_byok"
        assert owner_gemini_intelligence_enabled() is True
    finally:
        settings.asset_intelligence_transport = original
