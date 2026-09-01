"""Product Fidelity Guard v1 — prevention and visual QA."""

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from bebcare.config.settings import settings
from bebcare.database import Base, SessionLocal, engine
from bebcare.initial_data import initialize_data
from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.generation_run import GenerationArtifact, GenerationRun
from bebcare.models.user import User
from bebcare.schemas.generation_plan import build_generation_plan, dump_generation_plan
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
from bebcare.schemas.visual_fidelity import (
    VisualFidelityAssessment,
    VisualFidelityCheck,
    publication_decision_from_checks,
)
from bebcare.services.generation_plan import attach_generation_plan, executed_plan_contract
from bebcare.services.generation_run_store import add_artifacts, create_generation_run
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO
from bebcare.services.product_fidelity_prevention import (
    detect_capture_style,
    detect_unsupported_installations,
    evidence_installations,
    model_facing_image_label,
    physical_placement_sanitization_applies,
    sanitize_final_image_prompt,
    sanitize_realistic_photo_style,
    simplify_unsupported_placement,
)
from bebcare.services.visual_fidelity_qa import (
    cache_identity_from_material,
    cache_material,
    friendly_warning,
    persist_assessment,
    run_visual_fidelity_qa,
)
from bebcare.services.product_fidelity_rollout import (
    product_fidelity_prevention_mode,
    visual_fidelity_blocks_auto_publish,
    visual_fidelity_enabled,
    visual_fidelity_qa_mode,
)
from bebcare.services.quality_protection import apply_publish_gate, candidate_is_eligible


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "product_fidelity" / "motion_crib_rail_v1.json"


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
            ),
            ManifestItem(
                order=1,
                role="supporting_subject",
                image_id="ref-support",
                cdn_url="https://cdn.example.test/support.jpg",
                image_type="product",
                authority="suitability",
            ),
        ]
    )


def test_c4d_terms_removed_in_realistic_mode():
    cleaned, changed = sanitize_realistic_photo_style(
        "A C4D photorealistic 3D render with Octane render and magical product glow"
    )
    assert changed
    assert "c4d" not in cleaned.lower()
    assert "3d render" not in cleaned.lower()
    assert "octane" not in cleaned.lower()
    extra, extra_changed = sanitize_realistic_photo_style(
        "8K ultra-high-definition pristine flawless dreamy airy bokeh high-end e-commerce"
    )
    assert extra_changed
    assert "pristine" not in extra.lower()
    assert "8k ultra-high-definition" not in extra.lower()
    brief, brief_changed = sanitize_realistic_photo_style("8K ultra detail, commercial still")
    assert brief_changed
    assert "8k" not in brief.lower()
    lone, lone_changed = sanitize_realistic_photo_style("shot on 8k with natural light")
    assert lone_changed
    assert "8k" not in lone.lower()
    gold, gold_changed = sanitize_realistic_photo_style("18k gold trim on the bezel")
    assert "18k" in gold.lower()


def test_graphic_mode_keeps_render_language():
    info = {"capture_style": "graphic_or_illustrated"}
    assert detect_capture_style(info, ["illustration poster art"]) == "graphic_or_illustrated"
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        out = sanitize_final_image_prompt(
            "Unreal Engine render of a graphic campaign poster",
            {"source": SOURCE_STUDIO, "capture_style": "graphic_or_illustrated", "generation_plan": dump_generation_plan(build_generation_plan(_manifest()))},
        )
        assert "Unreal Engine render" in out or "unreal" in out.lower()
    finally:
        settings.product_fidelity_prevention_mode = original


def test_unsupported_mount_simplified_supported_mount_kept():
    text = "camera mounted on the crib-rail of a white crib"
    hits = detect_unsupported_installations(text, set())
    assert "crib_rail_mount" in hits
    simplified = simplify_unsupported_placement(text)
    assert "dresser" in simplified.lower() or "shelf" in simplified.lower()
    assert not detect_unsupported_installations(
        "attached using an unsupported clip mount",
        {"clip"},
    )
    stroller = "monitor clipped to the stroller near the handlebar"
    assert "stroller_mount" in detect_unsupported_installations(stroller, set())
    assert "stroller_mount" not in detect_unsupported_installations(stroller, {"stroller_mount"})
    assert not detect_unsupported_installations(
        "Includes a stroller attachment for travel",
        set(),
        product_info={"offering_type": "physical_product"},
    )
    assert not detect_unsupported_installations(
        "Baby monitor mounted on a stroller",
        set(),
        product_info={"offering_type": "stroller"},
    )


def _ensure_db():
    Base.metadata.create_all(bind=engine)
    initialize_data()


def _run(db, *, owner_id, source=SOURCE_STUDIO, **kwargs):
    defaults = dict(
        product_id=None,
        generate_task_id=None,
        rollout_mode_at_start="studio",
        experiment_variant=None,
        requested_pipeline_version="x",
        executed_pipeline_version="grounded_prompt_role_transport_v1",
        fallback_reason=None,
        fallback_path=None,
        image_prompt_pipeline=None,
        compare_group_id=None,
        provider_id="p",
        model="m",
        image_size="128x128",
        image_provider_mode="platform",
    )
    defaults.update(kwargs)
    return create_generation_run(db, owner_user_id=owner_id, source=source, **defaults)


def test_no_hardcoded_bebcare():
    files = [
        Path("bebcare/services/product_fidelity_prevention.py"),
        Path("bebcare/services/visual_fidelity_qa.py"),
        Path("bebcare/schemas/visual_fidelity.py"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "Bebcare" not in text
        assert "bebcare.com" not in text


def test_primary_authority_and_logo_policy_in_prompt():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        plan = dump_generation_plan(build_generation_plan(_manifest()))
        info = {
            "source": SOURCE_STUDIO,
            "generation_plan": plan,
            "generation_provenance": {"source": SOURCE_STUDIO, "reference_manifest": plan["reference_manifest"]},
            "brand_name": "AcmeCam",
            "logo_in_images": "composite",
            "logo_url": "https://cdn.example.test/logo.png",
        }
        out = sanitize_final_image_prompt("C4D 3D render on a crib-rail", info)
        assert "Image 1 is the primary geometry" in out
        assert "Image 1: primary_subject" in out
        assert "Image 2: supporting_subject" in out
        assert "Image 0" not in out
        assert 'The exact case-sensitive wordmark is "AcmeCam"' in out
        assert "capitalization" in out.lower()
        assert "c4d" not in out.lower()
        assert "crib-rail" not in out.lower()
        assert "AcmeCam" in str(info.get("generation_plan", {}).get("logo_policy") or info)
    finally:
        settings.product_fidelity_prevention_mode = original


def test_hidden_logo_language_present():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        plan = dump_generation_plan(build_generation_plan(_manifest()))
        out = sanitize_final_image_prompt(
            "lifestyle photo",
            {"source": SOURCE_STUDIO, "generation_plan": plan, "generation_provenance": {"source": SOURCE_STUDIO}},
        )
        assert "unobtrusive" in out.lower() or "absent" in out.lower()
    finally:
        settings.product_fidelity_prevention_mode = original


def test_prevention_off_does_not_rewrite_prompt():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "off"
    try:
        raw = "C4D photorealistic 3D render mounted on the crib-rail"
        assert sanitize_final_image_prompt(raw, {"source": SOURCE_STUDIO}) == raw
    finally:
        settings.product_fidelity_prevention_mode = original


def test_rollout_client_cannot_enable():
    original = settings.visual_fidelity_qa_mode
    settings.visual_fidelity_qa_mode = "off"
    try:
        assert not visual_fidelity_enabled(source=SOURCE_STUDIO, requested_mode="all")
        assert visual_fidelity_qa_mode() == "off"
    finally:
        settings.visual_fidelity_qa_mode = original


def test_visual_off_zero_calls():
    _ensure_db()
    db = SessionLocal()
    try:
        user = db.query(User).first()
        run = _run(db, owner_id=user.user_id, visual_fidelity_qa_mode="off")
        add_artifacts(db, run, ["https://cdn.example.test/out.jpg"])
        calls = {"n": 0}

        def assess(_payload):
            calls["n"] += 1
            raise AssertionError("should not call")

        original = settings.visual_fidelity_qa_mode
        settings.visual_fidelity_qa_mode = "off"
        try:
            summary = run_visual_fidelity_qa(
                db,
                {
                    "generation_run_id": run.run_id,
                    "owner_user_id": user.user_id,
                    "generation_plan": dump_generation_plan(build_generation_plan(_manifest())),
                },
                source=SOURCE_STUDIO,
                image_urls=["https://cdn.example.test/out.jpg"],
                assessor=assess,
            )
            assert summary["calls"] == 0
            assert calls["n"] == 0
        finally:
            settings.visual_fidelity_qa_mode = original
    finally:
        db.close()


def _assessment(**kwargs):
    checks = kwargs.pop("checks")
    return VisualFidelityAssessment(
        candidate_index=kwargs.get("candidate_index", 0),
        checks=checks,
        overall_publication_decision=publication_decision_from_checks(checks),
        model_version="test-vision",
        cache_hit=kwargs.get("cache_hit", False),
        correction_used=kwargs.get("correction_used", False),
    )


def test_distortion_and_logo_and_cgi_policy():
    import json

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    checks = [
        VisualFidelityCheck(check_code=code, status="hard_fail", confidence="high", short_reason="conflict", observed_evidence="candidate", reference_evidence="ref")
        for code in fixture["expected_hard_fail"]
    ]
    checks += [
        VisualFidelityCheck(check_code=code, status="warning", short_reason="style")
        for code in fixture["expected_warning"]
    ]
    checks.append(
        VisualFidelityCheck(
            check_code="severe_scene_mismatch",
            status="pass",
            short_reason="crib/child allowed",
        )
    )
    assessment = _assessment(checks=checks)
    assert assessment.overall_publication_decision == "blocked"
    codes = {c.check_code: c.status for c in assessment.checks}
    assert codes["severe_scene_mismatch"] == "pass"
    assert codes["strong_cgi_render_appearance"] == "warning"


def test_hidden_logo_and_hidden_antenna_not_hard_fail():
    checks = [
        VisualFidelityCheck(check_code="logo_spelling_or_case_mismatch", status="not_verifiable"),
        VisualFidelityCheck(check_code="antenna_or_major_feature_missing", status="not_verifiable"),
    ]
    assert publication_decision_from_checks(checks) == "eligible"


def test_supported_surface_passes_and_cgi_is_warning():
    checks = [
        VisualFidelityCheck(check_code="unsupported_mount_or_attachment", status="pass"),
        VisualFidelityCheck(check_code="strong_cgi_render_appearance", status="hard_fail"),
        VisualFidelityCheck(check_code="generic_ai_lifestyle_staging", status="warning"),
    ]
    from bebcare.schemas.visual_fidelity import normalize_check

    checks = [normalize_check(c) for c in checks]
    assert checks[1].status == "warning"
    assert publication_decision_from_checks(checks) == "eligible_with_warnings"


def test_sibling_candidate_and_all_fail_publish_gate():
    _ensure_db()
    db = SessionLocal()
    try:
        user = db.query(User).first()
        run = _run(
            db,
            owner_id=user.user_id,
            source=SOURCE_AUTOMATION,
            rollout_mode_at_start="all",
            quality_protection_mode="off",
            visual_fidelity_qa_mode="all",
        )
        add_artifacts(db, run, ["https://cdn.example.test/a.jpg", "https://cdn.example.test/b.jpg"])
        persist_assessment(
            db,
            run,
            _assessment(
                candidate_index=0,
                checks=[VisualFidelityCheck(check_code="base_or_housing_redesign", status="hard_fail", confidence="high")],
            ),
            cache_key="k0",
        )
        persist_assessment(
            db,
            run,
            _assessment(
                candidate_index=1,
                checks=[VisualFidelityCheck(check_code="unsupported_mount_or_attachment", status="pass")],
            ),
            cache_key="k1",
        )
        db.commit()
        gate = apply_publish_gate(
            db,
            owner_user_id=user.user_id,
            run_id=run.run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.example.test/a.jpg", "https://cdn.example.test/b.jpg"],
        )
        assert gate["blocked"] is False
        assert gate["selected_index"] == 1

        run2 = _run(
            db,
            owner_id=user.user_id,
            source=SOURCE_AUTOMATION,
            rollout_mode_at_start="all",
            visual_fidelity_qa_mode="auto_publish",
        )
        add_artifacts(db, run2, ["https://cdn.example.test/c.jpg"])
        persist_assessment(
            db,
            run2,
            _assessment(
                candidate_index=0,
                checks=[VisualFidelityCheck(check_code="total_reference_identity_loss", status="hard_fail", confidence="high")],
            ),
            cache_key="k2",
        )
        db.commit()
        gate_bad = apply_publish_gate(
            db,
            owner_user_id=user.user_id,
            run_id=run2.run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.example.test/c.jpg"],
        )
        assert gate_bad["blocked"] is True
    finally:
        db.close()


def test_cache_hit_and_one_correction_and_no_credits():
    _ensure_db()
    db = SessionLocal()
    try:
        user = db.query(User).first()
        run = _run(db, owner_id=user.user_id, visual_fidelity_qa_mode="studio")
        add_artifacts(db, run, ["https://cdn.example.test/out.jpg"])
        calls = {"n": 0}

        def assess(payload):
            calls["n"] += 1
            return _assessment(
                correction_used=True,
                checks=[VisualFidelityCheck(check_code="generic_ai_lifestyle_staging", status="warning")],
            )

        original = settings.visual_fidelity_qa_mode
        settings.visual_fidelity_qa_mode = "studio"
        try:
            info = {
                "generation_run_id": run.run_id,
                "owner_user_id": user.user_id,
                "generation_plan": dump_generation_plan(build_generation_plan(_manifest())),
                "_qa_candidate_hashes": ["abc"],
            }
            first = run_visual_fidelity_qa(
                db, info, source=SOURCE_STUDIO, image_urls=["https://cdn.example.test/out.jpg"], assessor=assess
            )
            second = run_visual_fidelity_qa(
                db, info, source=SOURCE_STUDIO, image_urls=["https://cdn.example.test/out.jpg"], assessor=assess
            )
            assert first["calls"] == 1
            assert first["correction_calls"] == 1
            assert first["credits_charged"] == 0
            assert first["byok"] is False
            assert second["calls"] == 0
            assert second["cache_hits"] >= 1
            assert calls["n"] == 1
        finally:
            settings.visual_fidelity_qa_mode = original
    finally:
        db.close()


def test_tenant_isolation_findings():
    _ensure_db()
    db = SessionLocal()
    try:
        a = db.query(User).first()
        b = User(
            username=f"iso-{uuid4().hex[:10]}",
            email=f"iso-{uuid4().hex[:10]}@example.test",
            hashed_password="x",
        )
        db.add(b)
        db.flush()
        run = _run(db, owner_id=a.user_id, visual_fidelity_qa_mode="studio")
        add_artifacts(db, run, ["https://cdn.example.test/out.jpg"])
        persist_assessment(
            db,
            run,
            _assessment(checks=[VisualFidelityCheck(check_code="base_or_housing_redesign", status="hard_fail", confidence="high")]),
            cache_key="iso",
        )
        db.commit()
        stolen = (
            db.query(GenerationArtifactQualityFinding)
            .filter(
                GenerationArtifactQualityFinding.generation_run_id == run.run_id,
                GenerationArtifactQualityFinding.owner_user_id == b.user_id,
            )
            .all()
        )
        assert stolen == []
    finally:
        db.close()


def test_plan_matches_sanitized_prompt_contract():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        plan = dump_generation_plan(build_generation_plan(_manifest()))
        info = {
            "source": SOURCE_STUDIO,
            "generation_plan": plan,
            "generation_provenance": {"source": SOURCE_STUDIO, "reference_manifest": plan["reference_manifest"]},
        }
        from bebcare.services.product_fidelity_prevention import apply_product_fidelity_prevention

        apply_product_fidelity_prevention(info)
        contract = executed_plan_contract(info)
        prompt = sanitize_final_image_prompt("golden hour on crib-rail C4D", info)
        assert "Image 1 is the primary geometry" in contract
        assert "Image 1 is the primary geometry" in prompt
    finally:
        settings.product_fidelity_prevention_mode = original


def test_low_confidence_hard_fail_becomes_warning():
    from bebcare.schemas.visual_fidelity import normalize_check

    check = normalize_check(
        VisualFidelityCheck(
            check_code="base_or_housing_redesign",
            status="hard_fail",
            confidence="low",
        )
    )
    assert check.status == "warning"
    assert publication_decision_from_checks([check]) == "eligible_with_warnings"


def test_physical_and_software_hard_fails():
    for code in (
        "product_silhouette_mismatch",
        "invented_major_component",
        "missing_major_component",
        "control_layout_mismatch",
        "major_proportion_mismatch",
        "logo_spelling_or_case_mismatch",
        "unsupported_mount_or_attachment",
        "primary_interface_corruption",
    ):
        assert publication_decision_from_checks(
            [VisualFidelityCheck(check_code=code, status="hard_fail", confidence="high")]
        ) == "blocked"


def test_persisted_off_ignores_current_env():
    _ensure_db()
    db = SessionLocal()
    try:
        user = db.query(User).first()
        run = _run(db, owner_id=user.user_id, visual_fidelity_qa_mode="off")
        add_artifacts(db, run, ["https://cdn.example.test/out.jpg"])
        calls = {"n": 0}

        def assess(_payload):
            calls["n"] += 1
            raise AssertionError("legacy run must not be re-interpreted")

        original = settings.visual_fidelity_qa_mode
        settings.visual_fidelity_qa_mode = "all"
        try:
            summary = run_visual_fidelity_qa(
                db,
                {
                    "generation_run_id": run.run_id,
                    "owner_user_id": user.user_id,
                    "generation_plan": dump_generation_plan(build_generation_plan(_manifest())),
                },
                source=SOURCE_STUDIO,
                image_urls=["https://cdn.example.test/out.jpg"],
                assessor=assess,
            )
            assert summary["calls"] == 0
            assert calls["n"] == 0
        finally:
            settings.visual_fidelity_qa_mode = original
    finally:
        db.close()


def test_findings_attach_to_correct_artifact():
    _ensure_db()
    db = SessionLocal()
    try:
        user = db.query(User).first()
        run = _run(db, owner_id=user.user_id, visual_fidelity_qa_mode="studio")
        add_artifacts(
            db,
            run,
            ["https://cdn.example.test/a.jpg", "https://cdn.example.test/b.jpg"],
        )
        db.flush()
        persist_assessment(
            db,
            run,
            _assessment(
                candidate_index=1,
                checks=[VisualFidelityCheck(check_code="control_layout_mismatch", status="hard_fail", confidence="high")],
            ),
            cache_key="art-1",
        )
        db.commit()
        arts = (
            db.query(GenerationArtifact)
            .filter(GenerationArtifact.run_id == run.run_id)
            .order_by(GenerationArtifact.candidate_index)
            .all()
        )
        rows = (
            db.query(GenerationArtifactQualityFinding)
            .filter(
                GenerationArtifactQualityFinding.generation_run_id == run.run_id,
                GenerationArtifactQualityFinding.qa_kind == "visual_fidelity",
            )
            .all()
        )
        assert len(rows) == 1
        assert rows[0].artifact_id == arts[1].artifact_id
        assert rows[0].check_code == "control_layout_mismatch"
    finally:
        db.close()


def test_adapter_malformed_bounded_and_no_byok():
    from bebcare.services import visual_fidelity_adapter as adapter
    from bebcare.services.asset_intelligence_policy import AnalysisFailure

    class Resp:
        def __init__(self, text, status=200):
            self.status_code = status
            self.content = text.encode("utf-8")
            self.text = text

    calls = {"n": 0, "bodies": []}

    def poster(body):
        calls["n"] += 1
        calls["bodies"].append(body)
        return Resp('{"choices":[{"message":{"content":"not-json"}}]}')

    original = adapter._http_post
    adapter._http_post = poster
    try:
        try:
            adapter.assess_visual_fidelity(
                {
                    "candidate_index": 0,
                    "candidate_url": "https://cdn.example.test/c.jpg",
                    "primary_reference_url": "https://cdn.example.test/p.jpg",
                    "supporting_reference_urls": ["https://cdn.example.test/s.jpg"],
                    "approved_logo_url": "https://cdn.example.test/logo.png",
                }
            )
            raise AssertionError("expected malformed failure")
        except AnalysisFailure as exc:
            assert exc.error_category == "visual_qa_malformed"
        assert calls["n"] == 2
        blob = str(calls["bodies"][0])
        assert "image_url" in blob
        assert "byok" not in blob.lower()
        assert "credits" not in blob.lower()
    finally:
        adapter._http_post = original


def _physical_info(extra=None):
    plan = dump_generation_plan(build_generation_plan(_manifest()))
    info = {
        "source": SOURCE_STUDIO,
        "offering_type": "physical_product",
        "generation_plan": plan,
        "generation_provenance": {"source": SOURCE_STUDIO, "reference_manifest": plan["reference_manifest"]},
    }
    if extra:
        info.update(extra)
    return info


def test_false_positive_install_phrases_unchanged():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        for phrase in (
            "The camera stands on a dresser",
            "A person stands beside the product",
            "A laptop stand appears on the desk",
            "A short video clip demonstrates the service",
            "Use case diagram",
            "clipped highlights",
            "USB-C connector",
            "illustrated product-design service",
        ):
            assert detect_unsupported_installations(phrase, set()) == []
            out = sanitize_final_image_prompt(phrase, _physical_info())
            assert phrase in out
    finally:
        settings.product_fidelity_prevention_mode = original


def test_crib_rail_and_clip_mount_still_simplified():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        crib = "Mounted on the side rail of a crib"
        assert "crib_rail_mount" in detect_unsupported_installations(crib, set())
        out = sanitize_final_image_prompt(crib, _physical_info())
        assert "Mounted on the side rail of a crib" not in out
        clip = "Attached using an unsupported clip mount"
        assert "clip" in detect_unsupported_installations(clip, set())
        out2 = sanitize_final_image_prompt(clip, _physical_info())
        assert "clip mount" not in out2.lower() or "stable surface" in out2.lower()
        assert not detect_unsupported_installations(clip, {"clip"})
    finally:
        settings.product_fidelity_prevention_mode = original


def test_non_physical_prompt_not_placement_rewritten():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        phrase = "Mounted on the side rail of a crib"
        info = _physical_info({"offering_type": "saas"})
        assert physical_placement_sanitization_applies(info, [phrase]) is False
        out = sanitize_final_image_prompt(phrase, info)
        assert phrase in out
    finally:
        settings.product_fidelity_prevention_mode = original


def test_packaging_offering_not_flagged():
    assert detect_unsupported_installations(
        "unsupported packaging on the table",
        set(),
        product_info={"structured_settings": {"packaging_is_offering": True}},
    ) == []


def test_no_model_facing_image_zero():
    assert model_facing_image_label(0) == "Image 1"
    assert model_facing_image_label(1) == "Image 2"
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        out = sanitize_final_image_prompt("lifestyle photo", _physical_info())
        assert "Image 0" not in out
        assert "Image 1: primary_subject" in out
        assert "Image 2: supporting_subject" in out
    finally:
        settings.product_fidelity_prevention_mode = original


def test_exact_mixed_case_wordmark_and_hidden_and_none():
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        mixed = sanitize_final_image_prompt(
            "lifestyle photo",
            _physical_info({"brand_wordmark": "AcmeCamX"}),
        )
        assert 'The exact case-sensitive wordmark is "AcmeCamX"' in mixed
        hidden = sanitize_final_image_prompt("lifestyle photo", _physical_info())
        assert "naturally hidden" in hidden.lower()
        none = sanitize_final_image_prompt("lifestyle photo", _physical_info())
        assert "No trusted wordmark string is available" in none
        composite = sanitize_final_image_prompt(
            "lifestyle photo",
            _physical_info({"logo_in_images": "composite", "logo_url": "https://cdn.example.test/logo.png", "brand_name": "AcmeCam"}),
        )
        assert "controlled compositing" in composite.lower()
        assert "Bebcare" not in mixed
    finally:
        settings.product_fidelity_prevention_mode = original


def test_composite_logo_mismatch_does_not_block():
    from bebcare.schemas.visual_fidelity import normalize_check

    check = normalize_check(
        VisualFidelityCheck(
            check_code="logo_spelling_or_case_mismatch",
            status="hard_fail",
            confidence="high",
        ),
        composite_logo=True,
    )
    assert check.status == "warning"
    housing = normalize_check(
        VisualFidelityCheck(
            check_code="base_or_housing_redesign",
            status="hard_fail",
            confidence="high",
        ),
        composite_logo=True,
    )
    assert housing.status == "hard_fail"


def test_unknown_confidence_does_not_hard_fail():
    from bebcare.schemas.visual_fidelity import normalize_check

    check = normalize_check(
        VisualFidelityCheck(check_code="base_or_housing_redesign", status="hard_fail", confidence="unknown")
    )
    assert check.status == "warning"
    high = normalize_check(
        VisualFidelityCheck(check_code="base_or_housing_redesign", status="hard_fail", confidence="high")
    )
    assert high.status == "hard_fail"


def test_hard_fail_warning_priority():
    assessment = _assessment(
        checks=[
            VisualFidelityCheck(check_code="strong_cgi_render_appearance", status="warning"),
            VisualFidelityCheck(
                check_code="base_or_housing_redesign",
                status="hard_fail",
                confidence="high",
            ),
        ]
    )
    message, code = friendly_warning(assessment)
    assert message == "Product details may differ from the reference"
    assert code == "fidelity_product"


def test_cache_identity_invalidation_and_hit():
    plan = dump_generation_plan(build_generation_plan(_manifest()))
    plan["logo_policy"] = {"logo_mode": "preserve", "wordmark_authority": "Acme"}
    base_kwargs = dict(
        candidate_hash="aaa",
        candidate_url="https://cdn.example.test/tmp.jpg",
        plan=plan,
        product_info={"logo_url": "https://cdn.example.test/logo.png"},
        model_version="vision-a",
        prompt_hash="prompt1",
    )
    hit = cache_identity_from_material(cache_material(**base_kwargs))
    same_bytes_new_url = cache_identity_from_material(
        cache_material(**{**base_kwargs, "candidate_url": "https://cdn.example.test/other.jpg"})
    )
    assert hit == same_bytes_new_url
    changed_bytes = cache_identity_from_material(cache_material(**{**base_kwargs, "candidate_hash": "bbb"}))
    assert changed_bytes != hit
    plan_primary = dump_generation_plan(build_generation_plan(_manifest()))
    plan_primary["reference_manifest"]["items"][0]["image_id"] = "other-primary"
    plan_primary["logo_policy"] = plan["logo_policy"]
    assert cache_identity_from_material(cache_material(**{**base_kwargs, "plan": plan_primary})) != hit
    plan_support = dump_generation_plan(build_generation_plan(_manifest()))
    plan_support["reference_manifest"]["items"][1]["order"] = 9
    plan_support["logo_policy"] = plan["logo_policy"]
    assert cache_identity_from_material(cache_material(**{**base_kwargs, "plan": plan_support})) != hit
    assert (
        cache_identity_from_material(
            cache_material(**{**base_kwargs, "product_info": {"logo_url": "https://cdn.example.test/logo2.png"}})
        )
        != hit
    )
    plan_logo = dict(plan)
    plan_logo["logo_policy"] = {"logo_mode": "composite", "wordmark_authority": "Acme"}
    assert cache_identity_from_material(cache_material(**{**base_kwargs, "plan": plan_logo})) != hit
    plan_mark = dict(plan)
    plan_mark["logo_policy"] = {"logo_mode": "preserve", "wordmark_authority": "ACME"}
    assert cache_identity_from_material(cache_material(**{**base_kwargs, "plan": plan_mark})) != hit
    plan_changed = dict(plan)
    plan_changed["capture_style"] = "graphic_or_illustrated"
    assert cache_identity_from_material(cache_material(**{**base_kwargs, "plan": plan_changed})) != hit
    assert cache_identity_from_material(cache_material(**{**base_kwargs, "prompt_hash": "prompt2"})) != hit
    assert cache_identity_from_material(cache_material(**{**base_kwargs, "model_version": "vision-b"})) != hit


def test_tenant_cannot_load_or_reuse_other_owner_findings():
    _ensure_db()
    db = SessionLocal()
    try:
        a = db.query(User).first()
        b = User(
            username=f"iso2-{uuid4().hex[:10]}",
            email=f"iso2-{uuid4().hex[:10]}@example.test",
            hashed_password="x",
        )
        db.add(b)
        db.flush()
        run_a = _run(db, owner_id=a.user_id, visual_fidelity_qa_mode="studio")
        add_artifacts(db, run_a, ["https://cdn.example.test/out.jpg"])
        persist_assessment(
            db,
            run_a,
            _assessment(
                checks=[
                    VisualFidelityCheck(
                        check_code="base_or_housing_redesign",
                        status="hard_fail",
                        confidence="high",
                    )
                ]
            ),
            cache_key="secret-cache",
        )
        db.commit()
        stolen_rows = (
            db.query(GenerationArtifactQualityFinding)
            .filter(
                GenerationArtifactQualityFinding.cache_key == "secret-cache",
                GenerationArtifactQualityFinding.owner_user_id == b.user_id,
            )
            .all()
        )
        assert stolen_rows == []
        owned = (
            db.query(GenerationArtifactQualityFinding)
            .filter(
                GenerationArtifactQualityFinding.cache_key == "secret-cache",
                GenerationArtifactQualityFinding.owner_user_id == a.user_id,
            )
            .all()
        )
        assert owned
        calls = {"n": 0}

        def assess(_payload):
            calls["n"] += 1
            return _assessment(
                checks=[VisualFidelityCheck(check_code="generic_ai_lifestyle_staging", status="warning")]
            )

        original = settings.visual_fidelity_qa_mode
        settings.visual_fidelity_qa_mode = "studio"
        try:
            skipped = run_visual_fidelity_qa(
                db,
                {
                    "generation_run_id": run_a.run_id,
                    "owner_user_id": b.user_id,
                    "generation_plan": dump_generation_plan(build_generation_plan(_manifest())),
                },
                source=SOURCE_STUDIO,
                image_urls=["https://cdn.example.test/out.jpg"],
                assessor=assess,
            )
            assert skipped["calls"] == 0
            assert calls["n"] == 0
            run_b = _run(db, owner_id=b.user_id, visual_fidelity_qa_mode="studio")
            add_artifacts(db, run_b, ["https://cdn.example.test/out.jpg"])
            other = run_visual_fidelity_qa(
                db,
                {
                    "generation_run_id": run_b.run_id,
                    "owner_user_id": b.user_id,
                    "generation_plan": dump_generation_plan(build_generation_plan(_manifest())),
                    "_qa_candidate_hashes": ["abc"],
                },
                source=SOURCE_STUDIO,
                image_urls=["https://cdn.example.test/out.jpg"],
                assessor=assess,
            )
            assert other["calls"] == 1
        finally:
            settings.visual_fidelity_qa_mode = original
    finally:
        db.close()
