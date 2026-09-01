"""Logo Placement Guard: identity vs placement, numbering, overlay, QA."""

from bebcare.config.settings import settings
from bebcare.providers.generate_request import GenerateImageRequest
from bebcare.schemas.logo_placement import LogoIdentity, LogoObservation, LogoPlacementEvidence
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
from bebcare.schemas.visual_fidelity import publication_decision_from_checks
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO
from bebcare.services.logo_placement import (
    NO_GENERATE_BRANDING,
    approved_logo_usable,
    evaluate_logo_observation,
    generated_branding_blocks_overlay,
    include_wordmark_in_generation_prompt,
    model_facing_provider_labels,
    should_overlay_approved_logo,
    stored_role_line,
)
from bebcare.services.product_fidelity_prevention import sanitize_final_image_prompt
from bebcare.services.visual_fidelity_qa import cache_identity_from_material, cache_material


def _items_order_one_based():
    return [
        {"order": 1, "role": "primary_subject", "cdn_url": "https://cdn.example.test/p.jpg", "image_id": "p"},
        {"order": 2, "role": "supporting_subject", "cdn_url": "https://cdn.example.test/s.jpg", "image_id": "s"},
        {"order": 3, "role": "scene", "cdn_url": "https://cdn.example.test/sc.jpg", "image_id": "sc"},
    ]


def test_provider_labels_ignore_one_based_stored_order():
    labels = model_facing_provider_labels(_items_order_one_based())
    assert labels[0][0] == 1
    assert labels[0][1]["role"] == "primary_subject"
    line = stored_role_line(_items_order_one_based())
    assert line == "Image 1: primary_subject; Image 2: supporting_subject; Image 3: scene"
    assert "Image 0" not in line
    contradictory = (
        "Image 1 is the primary geometry and identity authority. "
        "Stored roles: Image 2: primary_subject; Image 3: supporting_subject"
    )
    fixed_roles = stored_role_line(_items_order_one_based())
    assert "Image 2: primary_subject" not in f"Image 1 is primary. Stored roles: {fixed_roles}"
    assert "Image 1: primary_subject" in fixed_roles


def test_generate_request_labels_match_payload_order():
    req = GenerateImageRequest(
        prompt="redraw",
        annotate_roles=True,
        references=ReferenceManifest(
            items=[
                ManifestItem(order=1, role="primary_subject", cdn_url="https://cdn.example.test/p.jpg", image_type="product", authority="suitability"),
                ManifestItem(order=2, role="scene", cdn_url="https://cdn.example.test/sc.jpg", image_type="scene", authority="suitability"),
            ]
        ),
    )
    labeled = req.prompt_with_role_labels()
    assert labeled.startswith("Image 1 (primary subject). Image 2 (scene context).")
    assert "Image 0" not in labeled


def test_wordmark_omitted_for_composite_and_weak_placement():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        info = {
            "source": SOURCE_STUDIO,
            "offering_type": "physical_product",
            "brand_wordmark": "AcmeCam",
            "logo_in_images": "composite",
            "logo_url": "https://cdn.example.test/logo.png",
            "generation_provenance": {"source": SOURCE_STUDIO},
        }
        prompt = sanitize_final_image_prompt("lifestyle photo", info)
        assert "AcmeCam" not in prompt
        assert NO_GENERATE_BRANDING.split(",")[0] in prompt
        assert include_wordmark_in_generation_prompt(info) is False
        software = dict(info, offering_type="software", logo_in_images="preserve")
        assert include_wordmark_in_generation_prompt(software) is True
        graphic = dict(info, offering_type="physical_product", capture_style="graphic_or_illustrated", logo_in_images="preserve")
        assert include_wordmark_in_generation_prompt(graphic) is True
    finally:
        settings.product_fidelity_prevention_mode = original


def test_camera_head_logo_hard_fails_despite_correct_spelling():
    evidence = LogoPlacementEvidence(
        logo_present="present",
        product_region="base_front",
        visibility_class="clearly_visible",
        confidence="high",
        candidate_view_supports_region=True,
    )
    observation = LogoObservation(
        present=True,
        product_region="left_side",
        count=1,
        spelling="AcmeCam",
        generated_mark=True,
    )
    checks = evaluate_logo_observation(
        observation=observation,
        evidence=evidence,
        identity=LogoIdentity(wordmark="AcmeCam"),
    )
    codes = {c.check_code for c in checks}
    assert "logo_on_unsupported_surface" in codes
    assert "logo_spelling_or_case_mismatch" not in codes
    assert publication_decision_from_checks(checks) == "blocked"
    assert generated_branding_blocks_overlay(checks)


def test_mirrored_surface_does_not_inherit():
    checks = evaluate_logo_observation(
        observation=LogoObservation(present=True, product_region="right_side", count=1),
        evidence=LogoPlacementEvidence(
            product_region="left_side",
            visibility_class="clearly_visible",
            confidence="high",
            candidate_view_supports_region=True,
        ),
    )
    assert any(c.check_code == "mirrored_logo" for c in checks)


def test_second_and_duplicate_logo_hard_fail():
    checks = evaluate_logo_observation(
        observation=LogoObservation(present=True, product_region="base_front", count=2),
        evidence=LogoPlacementEvidence(product_region="base_front", visibility_class="clearly_visible", confidence="high", candidate_view_supports_region=True),
    )
    assert any(c.check_code == "duplicated_logo" for c in checks)


def test_hidden_and_tiny_logo():
    hidden = evaluate_logo_observation(
        observation=LogoObservation(present=False),
        evidence=LogoPlacementEvidence(visibility_class="naturally_hidden", product_region="base_front", confidence="medium"),
    )
    assert hidden[0].status == "not_verifiable"
    tiny = evaluate_logo_observation(
        observation=LogoObservation(present=True, product_region="base_front"),
        evidence=LogoPlacementEvidence(visibility_class="tiny_or_unverifiable", product_region="base_front", confidence="low"),
    )
    assert any(c.status == "warning" for c in tiny)


def test_evidenced_base_front_passes():
    checks = evaluate_logo_observation(
        observation=LogoObservation(present=True, product_region="base_front", count=1, spelling="AcmeCam"),
        evidence=LogoPlacementEvidence(
            product_region="base_front",
            visibility_class="clearly_visible",
            confidence="high",
            candidate_view_supports_region=True,
        ),
        identity=__import__("bebcare.schemas.logo_placement", fromlist=["LogoIdentity"]).LogoIdentity(wordmark="AcmeCam"),
    )
    assert checks == []


def test_no_evidence_means_omit_not_invent():
    ok, reason = should_overlay_approved_logo(
        {
            "logo_in_images": "composite",
            "logo_url": "https://cdn.example.test/logo.png",
            "owner_user_id": "owner-a",
        }
    )
    assert ok is False
    assert reason == "placement_unreliable"


def test_foreign_tenant_logo_rejected():
    assert approved_logo_usable(
        {
            "owner_user_id": "owner-a",
            "logo_url": "https://cdn.example.test/logo.png",
            "logo_owner_user_id": "owner-b",
        }
    ) is False
    assert approved_logo_usable(
        {
            "owner_user_id": "owner-a",
            "logo_url": "https://cdn.example.test/logo.png",
            "logo_owner_user_id": "owner-a",
        }
    ) is True


def test_cache_changes_with_placement_and_stage():
    plan = {
        "logo_policy": {"logo_mode": "composite", "logo_placement": {"product_region": "base_front"}},
        "logo_placement": {"product_region": "base_front"},
        "reference_manifest": {"items": []},
    }
    a = cache_identity_from_material(
        cache_material(candidate_hash="h1", candidate_url="u", plan=plan, product_info={}, model_version="m", prompt_hash="p")
    )
    plan2 = {
        "logo_policy": {"logo_mode": "composite", "logo_placement": {"product_region": "left_side"}},
        "logo_placement": {"product_region": "left_side"},
        "reference_manifest": {"items": []},
    }
    b = cache_identity_from_material(
        cache_material(candidate_hash="h1", candidate_url="u", plan=plan2, product_info={}, model_version="m", prompt_hash="p")
    )
    assert a != b
    pre = cache_identity_from_material(
        cache_material(
            candidate_hash="h1",
            candidate_url="u",
            plan=plan,
            product_info={},
            model_version="m",
            prompt_hash="p",
            extra={"qa_stage": "pre_composite"},
        )
    )
    post = cache_identity_from_material(
        cache_material(
            candidate_hash="h1",
            candidate_url="u",
            plan=plan,
            product_info={},
            model_version="m",
            prompt_hash="p",
            extra={"qa_stage": "post_composite"},
        )
    )
    assert pre != post


def test_visual_fidelity_off_makes_zero_calls():
    from bebcare.services.product_fidelity_rollout import visual_fidelity_enabled

    original = settings.visual_fidelity_qa_mode
    settings.visual_fidelity_qa_mode = "off"
    try:
        assert visual_fidelity_enabled(source=SOURCE_STUDIO) is False
        assert visual_fidelity_enabled(source=SOURCE_AUTOMATION) is False
    finally:
        settings.visual_fidelity_qa_mode = original


def test_packaging_and_graphic_keep_wordmark_policy():
    packaging = {
        "offering_type": "packaging",
        "brand_wordmark": "BoxCo",
        "logo_in_images": "composite",
    }
    assert include_wordmark_in_generation_prompt(packaging) is True
    software = {
        "offering_type": "software",
        "brand_wordmark": "AppCo",
        "logo_in_images": "composite",
    }
    assert include_wordmark_in_generation_prompt(software) is True


def test_overlay_when_placement_strongly_evidenced():
    ok, reason = should_overlay_approved_logo(
        {
            "logo_in_images": "composite",
            "logo_url": "https://cdn.example.test/logo.png",
            "owner_user_id": "owner-a",
            "logo_owner_user_id": "owner-a",
            "logo_placement": {
                "product_region": "base_front",
                "visibility_class": "clearly_visible",
                "confidence": "high",
                "candidate_view_supports_region": True,
                "logo_present": "present",
            },
        }
    )
    assert ok is True
    assert reason == "evidenced_region"
    blocked, why = should_overlay_approved_logo(
        {
            "logo_in_images": "composite",
            "logo_url": "https://cdn.example.test/logo.png",
            "owner_user_id": "owner-a",
            "logo_owner_user_id": "owner-a",
            "logo_placement": {
                "product_region": "base_front",
                "visibility_class": "clearly_visible",
                "confidence": "high",
                "candidate_view_supports_region": True,
                "logo_present": "present",
            },
        },
        generated_branding_conflict=True,
    )
    assert blocked is False
    assert why == "pre_composite_generated_mark"


def test_camera_head_fixture():
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "logo_placement" / "camera_head_side_v1.json").read_text(
            encoding="utf-8"
        )
    )
    checks = evaluate_logo_observation(
        observation=LogoObservation.model_validate(fixture["observation"]),
        evidence=LogoPlacementEvidence.model_validate(fixture["evidence"]),
        identity=LogoIdentity(wordmark=fixture["wordmark"]),
    )
    codes = {c.check_code for c in checks if c.status == "hard_fail"}
    for expected in fixture["expected_hard_fail"]:
        assert expected in codes
    assert publication_decision_from_checks(checks) == "blocked"


def test_adapter_labels_are_unambiguous():
    from bebcare.services.visual_fidelity_adapter import _vision_user_content

    parts = _vision_user_content(
        {
            "candidate_url": "data:image/jpeg;base64,QQ==",
            "primary_reference_url": "data:image/jpeg;base64,QQ==",
            "approved_logo_url": "data:image/jpeg;base64,QQ==",
            "supporting_reference_urls": ["data:image/jpeg;base64,QQ=="],
            "reference_labels": {
                "candidate": "Candidate image",
                "primary": "Primary reference, Image 1",
                "supporting": ["Supporting reference, Image 2"],
                "approved_logo": "Approved logo asset",
            },
            "plan_summary": {},
            "logo_policy": {"wordmark_authority": "AcmeCam"},
        }
    )
    texts = [p.get("text") for p in parts if p.get("type") == "text"]
    blob = " ".join(str(t) for t in texts)
    assert "Candidate image" in blob
    assert "Primary reference, Image 1" in blob
    assert "Supporting reference, Image 2" in blob
    assert "Approved logo asset" in blob
    assert "Image 0" not in blob
    assert "wordmark_authority" in blob


def test_sanitized_prompt_roles_match_provider_order():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        from bebcare.schemas.generation_plan import build_generation_plan, dump_generation_plan

        plan = dump_generation_plan(
            build_generation_plan(
                ReferenceManifest(
                    items=[
                        ManifestItem(
                            order=0,
                            role="primary_subject",
                            cdn_url="https://cdn.example.test/p.jpg",
                            image_type="product",
                            authority="suitability",
                        ),
                        ManifestItem(
                            order=1,
                            role="supporting_subject",
                            cdn_url="https://cdn.example.test/s.jpg",
                            image_type="product",
                            authority="suitability",
                        ),
                    ]
                )
            )
        )
        prompt = sanitize_final_image_prompt(
            "lifestyle photo",
            {
                "source": SOURCE_STUDIO,
                "offering_type": "physical_product",
                "brand_wordmark": "AcmeCam",
                "logo_in_images": "composite",
                "generation_plan": plan,
                "generation_provenance": {"source": SOURCE_STUDIO, "reference_manifest": plan["reference_manifest"]},
            },
        )
        assert "Image 1: primary_subject" in prompt
        assert "Image 2: supporting_subject" in prompt
        assert "Image 1 is the product-geometry authority" in prompt
        assert "Stored roles: Image 2: primary_subject" not in prompt
        assert "AcmeCam" not in prompt
        assert "Image 0" not in prompt
        assert "Do not add branding to another surface" in prompt or "not support it" in prompt
    finally:
        settings.product_fidelity_prevention_mode = original

