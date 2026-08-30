import pytest

from bebcare.schemas.generation_plan import build_generation_plan, render_generation_plan_contract
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest


def _manifest(*items: ManifestItem) -> ReferenceManifest:
    return ReferenceManifest(items=list(items))


def test_single_primary_plan():
    plan = build_generation_plan(
        _manifest(
            ManifestItem(
                order=0,
                role="primary_subject",
                image_id="p1",
                cdn_url="https://cdn.test/p.jpg",
                image_type="product",
                authority="preferred",
            )
        )
    )
    assert plan.display_config == "single_primary"
    assert plan.subject.primary_subject_count == 1
    assert plan.subject.duplicate_primary_subjects_allowed is False
    assert plan.handheld_physical_replacement == "prohibited"
    assert plan.subject.physical_instance_limit is None
    assert plan.display_configuration == "single_primary"
    assert plan.subject_spec.primary_subject_count == 1
    assert "duplicate_primary_subjects" in plan.forbidden_changes
    assert "scene_consistent_perspective" in plan.allowed_changes


def test_multi_reference_same_subject():
    plan = build_generation_plan(
        _manifest(
            ManifestItem(
                order=0,
                role="primary_subject",
                image_id="p1",
                cdn_url="https://cdn.test/p.jpg",
                image_type="product",
                authority="suitability",
            ),
            ManifestItem(
                order=1,
                role="supporting_subject",
                image_id="p2",
                cdn_url="https://cdn.test/p2.jpg",
                image_type="product",
                authority="suitability",
            ),
        )
    )
    assert plan.display_config == "multi_reference_same_subject"
    assert plan.subject.supporting_subject_policy == "same_offering_only"


def test_scene_context():
    plan = build_generation_plan(
        _manifest(
            ManifestItem(
                order=0,
                role="primary_subject",
                image_id="p1",
                cdn_url="https://cdn.test/p.jpg",
                image_type="product",
                authority="preferred",
            ),
            ManifestItem(
                order=1,
                role="scene",
                image_id="s1",
                cdn_url="https://cdn.test/s.jpg",
                image_type="scene",
                authority="suitability",
            ),
        )
    )
    assert plan.display_config == "scene_context"
    assert plan.scene_mode == "lifestyle"


def test_group_rejected_without_evidence():
    manifest = _manifest(
        ManifestItem(
            order=0,
            role="primary_subject",
            image_id="p1",
            cdn_url="https://cdn.test/p.jpg",
            image_type="product",
            authority="suitability",
        )
    )
    with pytest.raises(ValueError, match="explicit group evidence"):
        build_generation_plan(manifest, requested_display_config="reference_supported_group")


def test_group_allowed_with_structured_settings():
    plan = build_generation_plan(
        _manifest(
            ManifestItem(
                order=0,
                role="primary_subject",
                image_id="p1",
                cdn_url="https://cdn.test/p.jpg",
                image_type="product",
                authority="suitability",
            )
        ),
        structured_group={"kind": "set"},
    )
    assert plan.display_config == "reference_supported_group"
    assert plan.subject.supporting_subject_policy == "explicit_group"
    assert plan.subject.physical_instance_limit is None
    assert plan.subject.primary_subject_count == 1


def test_supporting_refs_do_not_infer_group():
    plan = build_generation_plan(
        _manifest(
            ManifestItem(
                order=0,
                role="primary_subject",
                cdn_url="https://cdn.test/p.jpg",
                image_type="product",
                authority="suitability",
            ),
            ManifestItem(
                order=1,
                role="supporting_subject",
                cdn_url="https://cdn.test/p2.jpg",
                image_type="product",
                authority="suitability",
            ),
            ManifestItem(
                order=2,
                role="supporting_subject",
                cdn_url="https://cdn.test/p3.jpg",
                image_type="product",
                authority="suitability",
            ),
        )
    )
    assert plan.display_config == "multi_reference_same_subject"
    assert plan.subject.primary_subject_count == 1
    assert plan.subject.duplicate_primary_subjects_allowed is False
    text = render_generation_plan_contract(plan, "en")
    assert "must not produce duplicate primary subjects" in text


def test_physical_instance_limit_requires_evidence():
    manifest = _manifest(
        ManifestItem(
            order=0,
            role="primary_subject",
            cdn_url="https://cdn.test/p.jpg",
            image_type="product",
            authority="preferred",
        )
    )
    unknown = build_generation_plan(manifest)
    assert unknown.subject.physical_instance_limit is None

    saas = build_generation_plan(
        manifest,
        product_info={
            "structured_settings": {
                "offering_kind": "saas",
                "physical_instance_limit": 1,
            }
        },
    )
    assert saas.subject.physical_instance_limit is None

    physical = build_generation_plan(
        manifest,
        product_info={
            "structured_settings": {
                "offering_kind": "physical",
                "physical_instance_limit": 1,
            }
        },
    )
    assert physical.subject.physical_instance_limit == 1


def test_attach_skips_plan_when_rollout_ineligible():
    from bebcare.services.generation_plan import attach_generation_plan

    info = {
        "grounded_phase1b_enabled": False,
        "generation_provenance": {
            "grounded_phase1b_enabled": False,
            "reference_manifest": _manifest(
                ManifestItem(
                    order=0,
                    role="primary_subject",
                    cdn_url="https://cdn.test/p.jpg",
                    image_type="product",
                    authority="preferred",
                )
            ).model_dump(),
        },
    }
    assert attach_generation_plan(info) is None
    assert info.get("generation_plan") is None


def test_prompt_uses_stored_plan_dump():
    from bebcare.prompt_builder.prompt_engine import PromptEngine
    from bebcare.services.generation_plan import attach_generation_plan, dump_generation_plan

    manifest = _manifest(
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
    )
    info = {
        "locale": "en",
        "product_name": "Monitor",
        "grounded_phase1b_enabled": True,
        "generation_provenance": {
            "grounded_phase1b_enabled": True,
            "reference_manifest": manifest.model_dump(),
        },
    }
    plan = attach_generation_plan(info)
    assert plan is not None
    stored = info["generation_plan"]
    assert stored == dump_generation_plan(plan)
    text = PromptEngine().build_scene_reference_prompt(info, "instagram")["prompt"]
    assert stored["display_configuration"] in text
    assert "subject_spec.primary_subject_count=1" in text
    assert "environmental evidence" in text
    assert "Keep product position, angle, size, and appearance unchanged" not in text
    rebuilt = PromptEngine().build_scene_reference_prompt(
        {**info, "generation_plan": stored}, "instagram"
    )["prompt"]
    assert rebuilt == text
