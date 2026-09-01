"""Generation diagnostics from persisted evidence, not live settings."""

from types import SimpleNamespace

from bebcare.services.generation_diagnostics import (
    build_planned_diagnostics,
    build_run_diagnostics,
)
from bebcare.services.quality_diversity_rollout import STRATEGY_OFF, STRATEGY_QDS


def _run(**kwargs):
    defaults = dict(
        run_id="run-1",
        status="succeeded",
        requested_selector_strategy=STRATEGY_OFF,
        executed_selector_strategy=STRATEGY_OFF,
        fallback_reason=None,
        fallback_path=None,
        generation_plan=None,
        reference_manifest={"items": [{"image_type": "product", "image_id": "p1"}]},
        selection_seed=None,
        quality_protection_mode="off",
        quality_policy_version=None,
        product_fidelity_prevention_mode="off",
        visual_fidelity_qa_mode="off",
        visual_fidelity_policy_version=None,
        model="gemini-test",
        provider_type="google",
        image_provider_mode="byok",
        image_size="1:1",
        credits_charged=1,
        latency_ms=1200,
        error_category=None,
        executed_pipeline_version="grounded_prompt_role_transport_v1",
        owner_user_id="owner-1",
        product_id="prod-1",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _event(event_type, **kwargs):
    return SimpleNamespace(event_type=event_type, **kwargs)


def _artifact(**kwargs):
    defaults = dict(
        artifact_id="a1",
        candidate_index=0,
        selected=True,
        persistence_warning=None,
        cdn_url="https://cdn.example/x.jpg",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _finding(**kwargs):
    defaults = dict(
        check_code="ok",
        severity="info",
        passed=True,
        qa_kind="deterministic",
        stage="post_generation",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_configured_off_is_not_executed_qds():
    diag = build_run_diagnostics(
        _run(),
        events=[_event("qds_skipped")],
        selection=None,
        findings=[],
        artifacts=[_artifact()],
        include_technical=False,
    )
    diversity = next(row for row in diag.summary if row.key == "diversity")
    assert diversity.status == "off" or diversity.message_key in ("qds_off", "qds_skipped")
    assert diag.state == "completed"
    assert diag.technical is None


def test_qds_conservative_from_events_not_env():
    diag = build_run_diagnostics(
        _run(requested_selector_strategy=STRATEGY_QDS, executed_selector_strategy=STRATEGY_QDS, selection_seed="seed-1"),
        events=[
            _event("qds_enabled"),
            _event("conservative_top_selection"),
        ],
        selection=SimpleNamespace(coverage_class="limited", candidate_summary={"eligible_ids": ["p1"]}),
        findings=[],
        artifacts=[_artifact()],
        include_technical=True,
    )
    diversity = next(row for row in diag.summary if row.key == "diversity")
    assert diversity.message_key == "conservative_top"
    assert diag.technical["selection_seed"] == "seed-1"


def test_qds_weighted_pool():
    diag = build_run_diagnostics(
        _run(requested_selector_strategy=STRATEGY_QDS, executed_selector_strategy=STRATEGY_QDS),
        events=[_event("qds_enabled"), _event("weighted_selection")],
        selection=SimpleNamespace(
            coverage_class="strong",
            candidate_summary={"eligible_ids": ["a", "b", "c"], "effective_weights": {"a": 0.5}},
        ),
        findings=[],
        artifacts=[_artifact()],
        include_technical=True,
    )
    diversity = next(row for row in diag.summary if row.key == "diversity")
    assert diversity.message_key == "weighted_selection"
    assert "effective_weights" in (diag.technical or {})


def test_legacy_no_history():
    diag = build_run_diagnostics(
        _run(reference_manifest=None, executed_selector_strategy=None, generation_plan=None),
        events=[],
        selection=None,
        findings=[],
        artifacts=[],
        include_technical=True,
    )
    assert diag.has_history is False
    assert diag.summary[0].message_key == "no_detailed_history"


def test_visual_qa_unavailable_not_passed():
    diag = build_run_diagnostics(
        _run(quality_protection_mode="studio", visual_fidelity_qa_mode="studio"),
        events=[_event("qds_skipped")],
        selection=None,
        findings=[_finding(check_code="visual_qa_unavailable", severity="warning", passed=False, qa_kind="visual")],
        artifacts=[_artifact()],
        include_technical=False,
    )
    quality = next(row for row in diag.summary if row.key == "quality")
    assert quality.status == "unavailable"
    assert quality.message_key == "visual_qa_unavailable"


def test_hard_fail_blocks_and_cdn_is_warning():
    blocked = build_run_diagnostics(
        _run(quality_protection_mode="all"),
        events=[],
        selection=None,
        findings=[_finding(check_code="invalid_plan", severity="hard_fail", passed=False, stage="publish_gate")],
        artifacts=[_artifact()],
        include_technical=False,
    )
    quality = next(row for row in blocked.summary if row.key == "quality")
    assert quality.status == "blocked"
    cdn = build_run_diagnostics(
        _run(),
        events=[_event("qds_skipped")],
        selection=None,
        findings=[],
        artifacts=[_artifact(persistence_warning="upload_failed")],
        include_technical=False,
    )
    delivery = next(row for row in cdn.summary if row.key == "delivery")
    assert delivery.message_key == "cdn_persistence_warning"


def test_sibling_candidate_and_no_secrets():
    diag = build_run_diagnostics(
        _run(),
        events=[_event("qds_skipped")],
        selection=None,
        findings=[],
        artifacts=[
            _artifact(artifact_id="a0", candidate_index=0, selected=False),
            _artifact(artifact_id="a1", candidate_index=1, selected=True),
        ],
        include_technical=True,
    )
    delivery = next(row for row in diag.summary if row.key == "delivery")
    assert delivery.message_key == "sibling_selected"
    blob = str(diag.technical)
    assert "api_key" not in blob
    assert "cdn.example" not in blob


def test_planned_does_not_claim_completed_qds_execution():
    planned = build_planned_diagnostics(
        selection_payload={
            "executed_selector_strategy": STRATEGY_OFF,
            "requested_selector_strategy": STRATEGY_OFF,
            "manifest": {"items": [{"image_type": "product"}]},
            "selector_trace": {},
        }
    )
    assert planned.state == "planned"
    diversity = next(row for row in planned.summary if row.key == "diversity")
    assert diversity.status == "off"


def test_prompt_protection_from_plan():
    diag = build_run_diagnostics(
        _run(
            product_fidelity_prevention_mode="studio",
            generation_plan={
                "fidelity": {
                    "logo": {"generated_branding_prohibited": True, "insert_wordmark_in_prompt": False},
                    "realistic_photo_sanitizer": True,
                },
                "extra_constraints": ["unsupported_mount_removed", "stable_surface_fallback"],
            },
        ),
        events=[_event("qds_skipped")],
        selection=None,
        findings=[],
        artifacts=[_artifact()],
        include_technical=False,
    )
    protections = next(row for row in diag.summary if row.key == "protections")
    assert protections.status == "applied"
    codes = {item.code for item in diag.groups["protections"].items}
    assert "generated_branding_prohibited" in codes
    assert "unsupported_mount_removed" in codes
