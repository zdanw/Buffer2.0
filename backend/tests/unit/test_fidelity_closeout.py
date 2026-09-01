"""Product-fidelity closeout: mounts, usage, wordmark redaction, numbering."""

import json
from pathlib import Path

from bebcare.config.settings import settings
from bebcare.providers.generate_request import GenerateImageRequest
from bebcare.schemas.generation_plan import build_generation_plan, dump_generation_plan
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
from bebcare.schemas.visual_fidelity import publication_decision_from_checks
from bebcare.services.grounded_rollout import SOURCE_STUDIO
from bebcare.services.product_fidelity_prevention import (
    detect_unsupported_installations,
    detect_usage_violations,
    evaluate_physical_scene,
    provider_image_order_from_plan,
    redact_prohibited_wordmark,
    rewrite_vague_mount_language,
    sanitize_final_image_prompt,
)


HEADREST = Path(__file__).resolve().parents[1] / "fixtures" / "product_fidelity" / "vehicle_headrest_v1.json"


def _physical(**extra):
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
                    ManifestItem(
                        order=2,
                        role="scene",
                        cdn_url="https://cdn.example.test/sc.jpg",
                        image_type="scene",
                        authority="suitability",
                    ),
                ]
            )
        )
    )
    info = {
        "source": SOURCE_STUDIO,
        "offering_type": "physical_product",
        "generation_plan": plan,
        "generation_provenance": {"source": SOURCE_STUDIO, "reference_manifest": plan["reference_manifest"]},
    }
    info.update(extra)
    return info


def test_headrest_pouch_and_vague_mount_rewritten():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        info = _physical()
        text = (
            "camera mounted on a stable support and attached to the headrest beside a child seat "
            "with a carrying pouch while driving"
        )
        assert "headrest_mount" in detect_unsupported_installations(text, set(), product_info=info)
        assert "pouch" in detect_unsupported_installations(text, set(), product_info=info)
        assert "tray" in detect_unsupported_installations(
            "units on a wooden tray across the rear seat", set(), product_info=info
        )
        assert "active_driving" in detect_usage_violations(text, product_info=info)
        out = sanitize_final_image_prompt(text, info)
        assert "headrest" not in out.lower() or "Do not attach" in out
        assert "mounted on a stable support" not in out.lower()
        assert "parked and stationary" in out.lower()
        assert "Image 3 is the scene/environment reference" in out
        assert "Image 1: primary_subject" in out
        assert "Image 2: supporting_subject" in out
        assert "Image 0" not in out
        assert "Image 2: primary_subject" not in out
    finally:
        settings.product_fidelity_prevention_mode = original


def test_vehicle_headrest_fixture():
    fixture = json.loads(HEADREST.read_text(encoding="utf-8"))
    checks = evaluate_physical_scene(fixture["observation"])
    codes = {c.check_code for c in checks if c.status == "hard_fail"}
    for expected in fixture["expected_hard_fail"]:
        assert expected in codes
    assert publication_decision_from_checks(checks) == "blocked"
    parked = evaluate_physical_scene({"vehicle_present": True, "active_driving": False})
    assert parked == []


def test_wordmark_redacted_from_physical_prompt_kept_for_qa():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        info = _physical(brand_wordmark="AcmeCam", logo_in_images="composite")
        out = sanitize_final_image_prompt("A single AcmeCam camera on a table", info)
        assert "AcmeCam" not in out
        assert "Do not render, redraw, restyle, relocate, or invent" in out
        assert (info.get("brand_wordmark") == "AcmeCam")
        software = _physical(offering_type="software", brand_wordmark="AcmeCam", logo_in_images="preserve")
        kept = redact_prohibited_wordmark("AcmeCam login screen", software)
        assert "AcmeCam" in kept
    finally:
        settings.product_fidelity_prevention_mode = original


def test_software_and_packaging_ignore_mount_policy():
    software = {"offering_type": "software"}
    assert not detect_unsupported_installations(
        "app icon mounted on the wall of the onboarding screen",
        set(),
        product_info=software,
    )
    assert detect_usage_violations("while driving", product_info=software) == []
    packaging = {"offering_type": "packaging"}
    assert not detect_unsupported_installations(
        "shown in its retail box",
        set(),
        product_info=packaging,
    )


def test_trusted_mount_preserved():
    text = "Baby monitor mounted on a stroller"
    assert not detect_unsupported_installations(
        text, set(), product_info={"offering_type": "stroller"}
    )
    assert not detect_unsupported_installations(
        "clip mount on crib",
        {"clip"},
        product_info={"offering_type": "physical_product"},
    )


def test_provider_order_scene_is_image_3():
    info = _physical()
    order = provider_image_order_from_plan(info["generation_plan"])
    assert [row["image_n"] for row in order] == [1, 2, 3]
    assert order[0]["role"] == "primary_subject"
    assert order[0]["stored_order"] == 0
    assert order[2]["role"] == "scene"
    req = GenerateImageRequest(
        prompt="x",
        annotate_roles=True,
        references=ReferenceManifest.model_validate(info["generation_plan"]["reference_manifest"]),
    )
    labeled = req.prompt_with_role_labels()
    assert "Image 3 (scene context (environment only; not a product))" in labeled


def test_vague_language_rewritten_without_hardware_noun():
    cleaned = rewrite_vague_mount_language(
        "product securely positioned beside the seat using a scene-consistent stable support already evidenced"
    )
    assert "securely positioned beside" not in cleaned.lower()
    assert "original base" in cleaned.lower()
