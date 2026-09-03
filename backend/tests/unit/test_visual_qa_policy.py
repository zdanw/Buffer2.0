"""Visual QA production policy builder and branding/screen publication rules."""

from bebcare.schemas.generation_plan import build_generation_plan, dump_generation_plan
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
from bebcare.schemas.visual_fidelity import VisualFidelityCheck, normalize_check
from bebcare.services.logo_placement import include_wordmark_in_generation_prompt
from bebcare.services.product_fidelity_prevention import apply_product_fidelity_prevention
from bebcare.services.visual_qa_policy import (
    POLICY_BUILDER_ID,
    REQUIRED_QA_CHECK_CODES,
    build_visual_qa_policy,
    qa_payload_from_policy,
)


def _manifest():
    return ReferenceManifest(
        items=[
            ManifestItem(
                order=0,
                role="primary_subject",
                image_id="ref-primary",
                cdn_url="https://cdn.example.test/primary.jpg",
                image_type="product",
                authority="suitability",
            )
        ]
    )


def _studio_info(**extra):
    info = {
        "source": "studio",
        "offering_type": "physical_product",
        "generation_plan": dump_generation_plan(build_generation_plan(_manifest())),
        "generation_provenance": {"source": "studio"},
        "_sanitized_prompt_hash": "abc123",
        "brand_name": "Bebcare",
    }
    info.update(extra)
    return info


def test_visual_qa_receives_complete_production_policy():
    policy = build_visual_qa_policy(_studio_info())
    required = [
        "executed_generation_plan",
        "reference_manifest",
        "validated_final_prompt_hash",
        "reference_coverage",
        "offering_type",
        "subject_count_policy",
        "generated_branding_prohibited",
        "logo_mode",
        "approved_wordmark_for_comparison",
        "logo_placement_evidence",
        "screen_evidence_strength",
        "screen_content_policy",
        "unsupported_mount_accessory_cable_policy",
        "compositing_state",
        "qa_stage",
        "provider_image_labels",
        "required_check_codes",
    ]
    for key in required:
        assert key in policy, key
    assert policy["policy_builder"] == POLICY_BUILDER_ID
    for code in REQUIRED_QA_CHECK_CODES:
        assert code in policy["required_check_codes"]
    payload = qa_payload_from_policy(
        policy=policy,
        candidate_index=0,
        candidate_url="https://cdn.example.test/cand.jpg",
        primary={"cdn_url": "https://cdn.example.test/primary.jpg"},
        supporting=[],
        reference_labels={"candidate": "Candidate image"},
        composite_logo=False,
        owner_user_id="owner-1",
        approved_logo_url=None,
        asset_intelligence=[],
    )
    for key in required:
        assert payload.get(key) is not None or key in payload
    assert payload["executed_qa_policy"]["policy_builder"] == POLICY_BUILDER_ID


def test_benchmark_and_studio_use_same_qa_policy_builder():
    info = _studio_info()
    studio = apply_product_fidelity_prevention(dict(info))
    from_studio = build_visual_qa_policy(studio)
    from_raw = build_visual_qa_policy(info)
    assert from_studio["policy_builder"] == from_raw["policy_builder"] == POLICY_BUILDER_ID
    assert from_studio["generated_branding_prohibited"] == from_raw["generated_branding_prohibited"]
    assert include_wordmark_in_generation_prompt(studio) is False
    assert from_raw["insert_wordmark_in_generation_prompt"] is False
    if from_raw["generated_branding_prohibited"]:
        assert from_raw["insert_wordmark_in_generation_prompt"] is False


def test_generated_branding_prohibited_visible_wordmark_hard_fails():
    policy = {"generated_branding_prohibited": True}
    check = normalize_check(
        VisualFidelityCheck(
            check_code="invented_logo",
            status="hard_fail",
            confidence="high",
            short_reason="visible Bebcare wordmark",
            observed_evidence="generated wordmark on housing",
        ),
        policy=policy,
    )
    assert check.status == "hard_fail"
    assert check.publication_effect == "block"


def test_correctly_spelled_generated_branding_still_hard_fails():
    policy = {"generated_branding_prohibited": True}
    check = normalize_check(
        VisualFidelityCheck(
            check_code="invented_logo",
            status="hard_fail",
            confidence="medium",
            short_reason="matches approved Bebcare spelling",
            observed_evidence="exact wordmark",
        ),
        policy=policy,
    )
    assert check.status == "hard_fail"
    assert check.publication_effect == "block"


def test_absent_branding_passes():
    policy = {"generated_branding_prohibited": True}
    check = normalize_check(
        VisualFidelityCheck(
            check_code="invented_logo",
            status="pass",
            confidence="high",
            short_reason="no product lettering",
        ),
        policy=policy,
    )
    assert check.status == "pass"


def test_unsupported_live_screen_ui_hard_fails():
    policy = {
        "screen_evidence_strength": "weak",
        "screen_content_policy": "unsupported_invented_live_ui",
    }
    check = normalize_check(
        VisualFidelityCheck(
            check_code="prominent_ui_text_corruption",
            status="hard_fail",
            confidence="medium",
            short_reason="invented live feed UI",
            observed_evidence="readable live-feed dashboard",
        ),
        policy=policy,
    )
    assert check.status == "hard_fail"
    assert check.publication_effect == "block"


def test_dark_incidental_screen_passes_with_weak_evidence():
    policy = {"screen_evidence_strength": "weak", "screen_content_policy": "unsupported_invented_live_ui"}
    check = normalize_check(
        VisualFidelityCheck(
            check_code="prominent_screen_corruption",
            status="hard_fail",
            confidence="medium",
            short_reason="dark inactive display",
            observed_evidence="blank dark screen",
        ),
        policy=policy,
    )
    assert check.status == "pass"


def test_low_confidence_branding_becomes_warning():
    policy = {"generated_branding_prohibited": True}
    check = normalize_check(
        VisualFidelityCheck(
            check_code="invented_logo",
            status="hard_fail",
            confidence="low",
            short_reason="possible lettering",
        ),
        policy=policy,
    )
    assert check.status == "warning"
