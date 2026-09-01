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
        assert "handheld_request_removed" in report["resolved"]
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
    assert "coverage_viewpoint_restricted" in report["resolved"]


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
    assert "image_index_corrected" in report["resolved"]


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
