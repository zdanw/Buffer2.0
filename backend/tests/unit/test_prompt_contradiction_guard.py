"""Final Prompt Contradiction Guard: leftover instructions vs applied protections."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from bebcare.schemas.generation_plan import FORBIDDEN_CHANGES, GenerationPlan, dump_generation_plan
from bebcare.services.generation_diagnostics import build_run_diagnostics
from bebcare.services.grounded_rollout import SOURCE_STUDIO
from bebcare.services.product_fidelity_prevention import (
    fidelity_prompt_prefix,
    sanitize_final_image_prompt,
)
from bebcare.services.prompt_contradiction_guard import (
    POLICY_VERSION,
    apply_prompt_contradiction_guard,
    persist_prompt_contradiction,
)
from bebcare.config.settings import settings


def _plan(**extra):
    payload = dump_generation_plan(
        GenerationPlan(
            display_config="single_primary",
            forbidden_changes=list(FORBIDDEN_CHANGES),
        )
    )
    payload.update(extra)
    return payload


def _info(**extra):
    info = {
        "source": SOURCE_STUDIO,
        "product_id": "prod-1",
        "generation_run_id": "run-1",
        "generation_plan": _plan(),
        "generation_provenance": {"source": SOURCE_STUDIO},
    }
    info.update(extra)
    return info


def test_legacy_without_plan_is_unchanged():
    raw = "use hand-held replacement: swap the product in their hand. macro shot."
    out, report = apply_prompt_contradiction_guard(raw, {"source": SOURCE_STUDIO})
    assert out == raw
    assert report["evaluated"] is False
    assert report["applied"] is False


def test_handheld_request_removed_prohibition_kept():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "off"
    try:
        prompt = (
            "Handheld physical-product replacement is prohibited. "
            "use hand-held replacement: swap the product in their hand. "
            "Fingers must contact the product naturally."
        )
        out, report = apply_prompt_contradiction_guard(prompt, _info())
        assert "swap the product in their hand" not in out.lower()
        assert "fingers must contact the product" not in out.lower()
        assert "prohibited" in out.lower()
        assert report["applied"] is True
        assert "prompt" not in report
    finally:
        settings.product_fidelity_prevention_mode = original


def test_branding_contract_aligned_when_withheld():
    info = _info(
        generation_plan=_plan(
            logo_policy={"generated_branding_prohibited": True, "insert_wordmark_in_prompt": False}
        )
    )
    prompt = (
        "Preserve identity-defining structure, proportions, branding, and visible relationships. "
        "preserve visible branding=True. Copy the logo onto the front panel."
    )
    out, report = apply_prompt_contradiction_guard(prompt, info)
    assert "proportions, branding, and visible" not in out
    assert "Do not generate branding" in out
    assert "preserve visible branding=False" in out
    assert "Copy the logo onto the front panel" not in out
    assert report["applied"] is True


def test_coverage_drops_closeup_keeps_do_not_macro():
    info = _info(generation_plan=_plan(reference_coverage="limited", coverage_constraints=["no_macro"]))
    prompt = (
        "Stay close to the source camera angle. Do not use macro, mounting, handheld replacement. "
        "Extreme close-up hero. Dutch angle of the product."
    )
    out, report = apply_prompt_contradiction_guard(prompt, info)
    assert "Do not use macro" in out
    assert "extreme close-up hero" not in out.lower()
    assert "dutch angle" not in out.lower()
    assert report["applied"] is True


def test_variety_not_prefixed_when_coverage_limited():
    prefix = fidelity_prompt_prefix(
        {
            "reference_coverage": "limited",
            "coverage_constraints": ["no_macro"],
            "capture_style": "realistic_photography",
            "selector_trace": {"coverage": "limited"},
            "placement": {"instruction": "on a table"},
            "logo_policy": {},
        }
    )
    assert "Stay close to the source camera angle" in prefix
    assert "vary scene family, lighting, and palette" not in prefix


def test_graphic_campaign_keeps_render_language():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        out = sanitize_final_image_prompt(
            "Unreal Engine render of a graphic campaign poster",
            {
                "source": SOURCE_STUDIO,
                "capture_style": "graphic_or_illustrated",
                "generation_plan": {"capture_style": "graphic_or_illustrated"},
            },
        )
        assert "Unreal Engine render" in out or "unreal" in out.lower()
    finally:
        settings.product_fidelity_prevention_mode = original


def test_prevention_off_still_strips_grounded_handheld():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "off"
    try:
        out = sanitize_final_image_prompt(
            "use hand-held replacement: swap the product in their hand",
            _info(),
        )
        assert "swap the product in their hand" not in out.lower()
    finally:
        settings.product_fidelity_prevention_mode = original


def test_image_zero_corrected():
    out, report = apply_prompt_contradiction_guard("Use Image 0 as the product.", _info())
    assert "Image 0" not in out
    assert "Image 1" in out
    assert report["applied"] is True


def test_report_has_no_prompt_or_secrets():
    info = _info()
    info["api_key"] = "sk-secret"
    out, report = apply_prompt_contradiction_guard(
        "use hand-held replacement: swap the product in their hand sk-secret",
        info,
    )
    blob = str(report)
    assert "sk-secret" not in blob
    assert "swap the product" not in blob
    assert POLICY_VERSION in blob
    assert "swap the product" not in out.lower()


def test_diagnostics_maps_contradiction_applied():
    from tests.unit.test_generation_diagnostics import _artifact, _event, _run

    diag = build_run_diagnostics(
        _run(
            product_fidelity_prevention_mode="studio",
            generation_plan={
                "prompt_contradiction": {
                    "policy_version": POLICY_VERSION,
                    "evaluated": True,
                    "applied": True,
                    "resolved": ["handheld_request_removed"],
                }
            },
        ),
        events=[_event("prompt_contradiction_resolved")],
        selection=None,
        findings=[],
        artifacts=[_artifact()],
        include_technical=True,
    )
    codes = {item.code for item in diag.groups["protections"].items}
    assert "prompt_contradiction_resolved" in codes
    assert diag.technical["policy_versions"]["contradiction"] == POLICY_VERSION
    assert "sk-" not in str(diag.technical)
    assert "api_key" not in str(diag.technical)


def test_persist_failure_does_not_raise():
    db = MagicMock()
    db.query.side_effect = RuntimeError("db down")
    persist_prompt_contradiction(
        db,
        {
            "generation_run_id": "run-1",
            "generation_plan": {
                "prompt_contradiction": {
                    "policy_version": POLICY_VERSION,
                    "evaluated": True,
                    "applied": True,
                    "resolved": ["handheld_request_removed"],
                }
            },
        },
    )


def test_persist_skips_cross_owner():
    run = SimpleNamespace(run_id="run-1", owner_user_id="owner-a", generation_plan={})
    query = MagicMock()
    query.filter.return_value.first.return_value = run
    db = MagicMock()
    db.query.return_value = query
    persist_prompt_contradiction(
        db,
        {
            "generation_run_id": "run-1",
            "owner_user_id": "owner-b",
            "generation_plan": {
                "prompt_contradiction": {
                    "evaluated": True,
                    "applied": True,
                    "resolved": ["handheld_request_removed"],
                }
            },
        },
    )
    db.begin_nested.assert_not_called()


def _physical_info(**extra):
    return _info(offering_type="physical_product", **extra)


def test_vehicle_contradiction_rewritten_and_bound():
    from bebcare.providers.generate_request import GenerateImageRequest
    from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
    from bebcare.services.prompt_contradiction_guard import (
        prepare_validated_image_request,
        prompt_digest,
        validate_final_prompt,
    )

    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        info = _physical_info(
            generation_plan=_plan(
                reference_coverage="limited",
                coverage_constraints=["no_macro", "no_mounting"],
                capture_style="realistic_photography",
                logo_policy={"generated_branding_prohibited": True, "insert_wordmark_in_prompt": False},
                subject={"primary_subject_count": 1, "duplicate_primary_subjects_allowed": False},
            )
        )
        prompt = (
            "Place the complete original product on a dresser. Do not invent cables. "
            "Camera on a cushioned rear car seat. Monitor on the center console during a morning commute. "
            "A charging cable trailing to the console. Screen displaying a live nursery feed. "
            "Warm golden cinematic styling and dreamy shallow depth of field."
        )
        result = validate_final_prompt(prompt, info)
        text = result.validated_prompt.lower()
        assert result.evaluated is True
        assert result.changed is True
        assert result.provider_request_allowed is True
        assert "cushioned rear car seat" not in text
        assert "center console" not in text
        assert "morning commute" not in text
        assert "charging cable" not in text
        assert "live nursery feed" not in text
        assert "parked" in text or "stationary" in text
        assert "dresser" in text or "table" in text or "counter" in text
        assert result.persistable().get("validated_prompt") is None
        assert "cushioned rear" not in str(result.persistable())
        draft = GenerateImageRequest(
            prompt=prompt,
            annotate_roles=True,
            references=ReferenceManifest(
                items=[
                    ManifestItem(
                        order=0,
                        role="primary_subject",
                        cdn_url="https://cdn.test/p.jpg",
                        image_type="product",
                        authority="suitability",
                    ),
                ]
            ),
        )
        frozen, bound = prepare_validated_image_request(draft, info)
        assert frozen.validated_prompt_hash == bound.validated_prompt_hash
        assert prompt_digest(frozen.prompt_with_role_labels()) == frozen.validated_prompt_hash
        assert frozen.annotate_roles is False
        frozen2, bound2 = prepare_validated_image_request(draft, info)
        assert frozen2 is frozen
        assert bound2.validated_prompt_hash == bound.validated_prompt_hash
    finally:
        settings.product_fidelity_prevention_mode = original


def test_parked_vehicle_background_allowed():
    from bebcare.services.prompt_contradiction_guard import validate_final_prompt

    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        prompt = (
            "A parked vehicle is visible through the window. The product rests on an ordinary table "
            "outside the vehicle. No driver interaction."
        )
        result = validate_final_prompt(prompt, _physical_info())
        assert "parked vehicle" in result.validated_prompt.lower()
        assert "vehicle_usage_conflict" not in result.detected_conflicts
    finally:
        settings.product_fidelity_prevention_mode = original


def test_stroller_mount_rewritten_supported_kept():
    from bebcare.services.prompt_contradiction_guard import validate_final_prompt

    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        rewritten = validate_final_prompt(
            "The camera is mounted on the stroller frame.",
            _physical_info(),
        )
        assert "stroller frame" not in rewritten.validated_prompt.lower() or "Do not" in rewritten.validated_prompt
        assert rewritten.changed is True
        kept = validate_final_prompt(
            "Baby monitor mounted on a stroller near the handlebar.",
            _info(offering_type="stroller"),
        )
        assert "stroller" in kept.validated_prompt.lower()
    finally:
        settings.product_fidelity_prevention_mode = original


def test_software_and_packaging_exceptions():
    from bebcare.services.prompt_contradiction_guard import validate_final_prompt

    software = validate_final_prompt(
        "Software connector on the login screen with readable interface labels.",
        _info(offering_type="software", generation_plan=_plan(capture_style="graphic_or_illustrated")),
    )
    assert "connector" in software.validated_prompt.lower()
    packaging = validate_final_prompt(
        "Retail box printed with the product name on the packaging panel.",
        _info(offering_type="packaging", packaging_is_the_offering=True, generation_plan=_plan()),
    )
    assert "packaging" in packaging.validated_prompt.lower()


def test_subject_count_and_malformed_and_block():
    from bebcare.services.prompt_contradiction_guard import validate_final_prompt

    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        dup = validate_final_prompt(
            "Show two cameras beside each other as duplicate hero devices.",
            _physical_info(generation_plan=_plan(subject={"primary_subject_count": 1})),
        )
        assert "two cameras" not in dup.validated_prompt.lower()
        malformed = validate_final_prompt(
            "A lifestyle photograph white the product. lifestyle photograph, lifestyle photograph, 细腻质感",
            _physical_info(),
        )
        assert "white the product" not in malformed.validated_prompt.lower()
        assert "细腻质感" not in malformed.validated_prompt
        blocked = validate_final_prompt(
            "Image 1 (primary subject). Image 1 (scene context (environment only; not a product)).",
            _physical_info(),
        )
        assert blocked.provider_request_allowed is False
        assert "reference_authority_conflict" in blocked.hard_failures
        clean = validate_final_prompt(
            "A naturally captured lifestyle photograph of the product on a dresser.",
            _physical_info(),
        )
        assert clean.provider_request_allowed is True
    finally:
        settings.product_fidelity_prevention_mode = original


def test_legacy_rollout_off_without_plan_not_claimed():
    from bebcare.services.prompt_contradiction_guard import validate_final_prompt

    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "off"
    try:
        result = validate_final_prompt("Camera on a cushioned rear car seat.", {"source": SOURCE_STUDIO})
        assert result.evaluated is False
        assert result.diagnostics_summary == "prompt_contradiction_off"
        assert "cushioned" in result.validated_prompt.lower()
    finally:
        settings.product_fidelity_prevention_mode = original

