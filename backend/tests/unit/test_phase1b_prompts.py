from bebcare.prompt_builder.prompt_engine import PromptEngine
from bebcare.prompt_builder.prompt_locale import (
    grounded_re_render_contract,
    vision_scene_fusion_user_prompt_text_grounded,
    vision_scene_image_prompt_system_prompt,
    vision_scene_image_prompt_system_prompt_grounded,
)
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
from bebcare.services.generation_plan import attach_generation_plan


def _scene_plan_info():
    manifest = ReferenceManifest(
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
    )
    info = {
        "locale": "en",
        "product_name": "Baby Monitor",
        "grounded_phase1b_enabled": True,
        "generation_provenance": {
            "grounded_phase1b_enabled": True,
            "reference_manifest": manifest.model_dump(),
        },
    }
    attach_generation_plan(info)
    return info


def test_legacy_scene_prompt_still_mentions_handheld():
    text = vision_scene_image_prompt_system_prompt("en")
    assert "hand-held replacement" in text


def test_grounded_scene_prompt_forbids_handheld():
    info = _scene_plan_info()
    text = vision_scene_image_prompt_system_prompt_grounded("en", info)
    assert "Handheld physical-product replacement is prohibited" in text
    assert "hand-held replacement" not in text
    assert "Image 1 is the primary subject" in text
    assert "display_configuration=scene_context" in text
    zh = vision_scene_image_prompt_system_prompt_grounded("zh", info)
    assert "禁止手持实物替换" in zh


def test_grounded_user_prompt_has_no_grip_swap():
    info = _scene_plan_info()
    text = vision_scene_fusion_user_prompt_text_grounded(
        "Baby Monitor", "Video Monitor", "en", product_info=info
    )
    assert "replace the product in their hand" not in text
    assert "primary subject" in text
    assert "prohibited" in grounded_re_render_contract("en")
    assert "display_configuration=scene_context" in text


def test_grounded_legacy_scene_differs_from_rollout_off():
    engine = PromptEngine()
    off = engine.build_scene_reference_prompt(
        {
            "locale": "en",
            "product_name": "Baby Monitor",
            "grounded_phase1b_enabled": False,
        },
        "instagram",
    )["prompt"]
    grounded = engine.build_scene_reference_prompt(_scene_plan_info(), "instagram")["prompt"]
    assert "position, angle, size, and appearance unchanged" in off
    assert "position, angle, size, and appearance unchanged" not in grounded
    assert "Keep product position, angle, size, and appearance unchanged" in off
    assert "Controlled re-render" in grounded
    assert "Handheld physical-product replacement is prohibited" in grounded
    assert "scene-consistent perspective" in grounded
    assert "hand-held replacement" not in off
    assert off != grounded


def test_rollout_off_vision_prompt_keeps_handheld():
    off = vision_scene_image_prompt_system_prompt("en")
    grounded = vision_scene_image_prompt_system_prompt_grounded("en", _scene_plan_info())
    assert "hand-held replacement" in off
    assert "hand-held replacement" not in grounded
    assert off != grounded
