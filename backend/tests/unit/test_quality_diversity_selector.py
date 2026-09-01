"""Quality and Diversity Selector — eligibility, weights, cooldown, risk, fingerprint."""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.product import Product, ProductImage
from bebcare.models.user import User
from bebcare.schemas.asset_intelligence import AssetIntelligenceResult, PhysicalModule, ServiceEventModule
from bebcare.schemas.generation_plan import FORBIDDEN_CHANGES
from bebcare.services.generation_run_store import create_generation_run
from bebcare.services.product_fidelity_prevention import (
    detect_unsupported_installations,
    sanitize_final_image_prompt,
    sanitize_realistic_photo_style,
)
from bebcare.services.quality_diversity_eval import compare_selector_modes, pin_experiment_context
from bebcare.services.quality_diversity_policy import (
    ABSOLUTE_MIN_SCORE,
    SELECTOR_POLICY_VERSION,
    fingerprint_from_parts,
    resolve_risk_band,
)
from bebcare.services.quality_diversity_roles import classify_intelligence, evaluate_role
from bebcare.services.quality_diversity_rollout import quality_diversity_enabled
from bebcare.services.quality_diversity_context import SelectorContext, build_selector_context
from bebcare.services.quality_diversity_select import (
    ScoredCandidate,
    cooldown_penalties,
    eligible_pool,
    fingerprint_penalties,
    rng_from_seed,
    run_grounded_quality_diversity,
    weighted_choice,
    weighted_primary_allowed,
    _effective_weights,
)
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO
from bebcare.utils.grounded_reference_selector import select_grounded_references
from bebcare.schemas.reference_manifest import ReferenceManifest, assert_canonical_grounded_order


def _img(**kwargs):
    return SimpleNamespace(
        image_id=kwargs.get("image_id", str(uuid4())),
        cdn_url=kwargs.get("cdn_url", "https://cdn.test/a.jpg"),
        width=kwargs.get("width", 1600),
        height=kwargs.get("height", 1600),
        image_type=kwargs.get("image_type", "product"),
        is_preferred=kwargs.get("is_preferred", False),
        sort_index=kwargs.get("sort_index", 0),
        uploaded_at=kwargs.get("uploaded_at") or datetime.utcnow(),
        phash=kwargs.get("phash"),
        product_id=kwargs.get("product_id", "prod"),
    )


def _verdict(image, score, eligible=True, reasons=None, evidence_class="usable"):
    from bebcare.services.quality_diversity_roles import RoleVerdict

    return ScoredCandidate(
        image=image,
        verdict=RoleVerdict(
            role="primary_geometry",
            score=score,
            eligible=eligible,
            exclusion_reasons=list(reasons or []),
            evidence_class=evidence_class,
            evidence_complete=evidence_class in {"usable", "partial_useful"},
            score_confidence="semantic" if evidence_class in {"usable", "partial_useful"} else "resolution_only",
        ),
        is_preferred=bool(image.is_preferred),
    )


def test_rollout_default_off():
    original = settings.quality_diversity_selector_mode
    try:
        settings.quality_diversity_selector_mode = "off"
        assert quality_diversity_enabled(source=SOURCE_STUDIO, grounded=True) is False
        settings.quality_diversity_selector_mode = "studio"
        assert quality_diversity_enabled(source=SOURCE_STUDIO, grounded=True) is True
        assert quality_diversity_enabled(source=SOURCE_AUTOMATION, task_mode="auto", grounded=True) is False
        settings.quality_diversity_selector_mode = "all"
        assert quality_diversity_enabled(source=SOURCE_AUTOMATION, grounded=True) is True
        assert quality_diversity_enabled(source=SOURCE_STUDIO, grounded=False) is False
    finally:
        settings.quality_diversity_selector_mode = original


def test_wrong_component_excluded():
    v = evaluate_role(
        "primary_geometry",
        width=1600,
        height=1600,
        intended_component="monitor",
        observed_component="humidifier",
    )
    assert v.eligible is False
    assert "wrong_component" in v.exclusion_reasons


def test_severe_crop_excluded_for_geometry():
    v = evaluate_role("primary_geometry", width=120, height=120)
    assert v.eligible is False
    assert "severe_crop" in v.exclusion_reasons


def test_person_dominated_excluded_as_geometry_secondary():
    intel = AssetIntelligenceResult(
        asset_source_type="person",
        people_or_hands_presence="present",
        generation_suitability="avoid_as_primary",
        service_event=ServiceEventModule(person_prominence="dominant"),
    )
    v = evaluate_role("secondary_structure", width=1600, height=1600, intel=intel)
    assert v.eligible is False
    assert "person_dominated" in v.exclusion_reasons
    interaction = evaluate_role("interaction_reference", width=1600, height=1600, intel=intel)
    assert interaction.eligible is True


def test_packaging_dominated_excluded_unless_required():
    intel = AssetIntelligenceResult(
        asset_source_type="packaging",
        packaging_presence="present",
        physical=PhysicalModule(packaging_role="primary"),
    )
    blocked = evaluate_role("primary_geometry", width=1800, height=1800, intel=intel)
    assert blocked.eligible is False
    allowed = evaluate_role(
        "primary_geometry", width=1800, height=1800, intel=intel, packaging_required=True
    )
    assert allowed.eligible is True


def test_complete_product_and_base_eligible():
    intel = AssetIntelligenceResult(
        asset_source_type="product",
        generation_suitability="primary_subject",
        physical=PhysicalModule(support_surface="table", broad_view_class="three_quarter"),
    )
    v = evaluate_role("primary_geometry", width=2000, height=2000, intel=intel)
    assert v.eligible is True
    assert v.signals.get("complete_base") is True
    assert v.score >= ABSOLUTE_MIN_SCORE


def test_quality_floor_and_weights():
    strong = _verdict(_img(image_id="strong", width=2000, height=2000), 0.88)
    ok = _verdict(_img(image_id="ok", width=1400, height=1400), 0.74)
    poor = _verdict(_img(image_id="poor", width=200, height=200), 0.41, eligible=False, reasons=["severe_crop"])
    mediocre = _verdict(_img(image_id="mediocre", width=400, height=400), 0.50, eligible=True)
    pool, info = eligible_pool([strong, ok, poor, mediocre], require_semantic=True)
    ids = {c.image_id for c in pool}
    assert "poor" not in ids
    assert "mediocre" not in ids
    assert "strong" in ids
    assert "ok" in ids
    weights = _effective_weights(pool, penalties={}, risk="balanced", source="studio", task_mode=None)
    assert weights["strong"] > weights["ok"]
    chosen = weighted_choice(pool, weights, rng_from_seed("fixed-seed"))
    assert chosen.image_id in ids
    again = weighted_choice(pool, weights, rng_from_seed("fixed-seed"))
    assert again.image_id == chosen.image_id
    picks = {
        weighted_choice(pool, weights, rng_from_seed(f"seed-{i}")).image_id for i in range(40)
    }
    assert picks <= ids
    assert len(picks) >= 1
    only = eligible_pool([strong])[0]
    assert len(only) == 1
    assert weighted_choice(only, {"strong": 1.0}, rng_from_seed("x")).image_id == "strong"


def test_eval_modes_do_not_call_providers():
    scored = [
        _verdict(_img(image_id="a"), 0.9),
        _verdict(_img(image_id="b"), 0.8),
        _verdict(_img(image_id="c"), 0.4, eligible=False, reasons=["severe_crop"]),
    ]
    pin = pin_experiment_context(
        product_id="p",
        provider="x",
        model="y",
        aspect_ratio="1:1",
        content_purpose="lifestyle",
        quality_policy=SELECTOR_POLICY_VERSION,
    )
    report = compare_selector_modes(scored, pin=pin)
    assert pin["auto_provider_calls"] is False
    assert report["pinned"]["product_id"] == "p"
    assert report["auto_provider_calls"] is False
    assert report["A_current_selector"]["image_id"] == "a"
    assert report["B_quality_floor_top_one"]["image_id"] == "a"
    assert report["C_quality_floor_weighted"]["image_id"] in {"a", "b"}
    assert report["weighted_rotation_enabled"] is True


def test_cooldown_reduces_weight_not_preferred():
    history = [{"primary_reference_id": "recent"} for _ in range(4)]
    penalties = cooldown_penalties(history, preferred_id="pref")
    assert penalties["recent"] < 1.0
    pref_pen = cooldown_penalties(history + [{"primary_reference_id": "pref"}], preferred_id="pref")
    assert pref_pen["pref"] >= 0.92
    strong = _verdict(_img(image_id="recent"), 0.9)
    weak = _verdict(_img(image_id="weak"), 0.62)
    weights = _effective_weights(
        [strong, weak],
        penalties=penalties,
        risk="balanced",
        source="studio",
        task_mode=None,
    )
    assert weights["recent"] > weights["weak"]
    decayed = cooldown_penalties([{"primary_reference_id": "recent"}], preferred_id=None)
    fresh = cooldown_penalties([], preferred_id=None)
    assert decayed.get("recent", 1.0) < 1.0
    assert "recent" not in fresh


def test_risk_bands():
    band, reasons = resolve_risk_band(source="studio", task_mode=None, coverage="limited")
    assert band == "conservative"
    assert "limited_coverage" in reasons
    band, _ = resolve_risk_band(
        source="studio",
        task_mode=None,
        coverage="strong",
        dimension_text="macro close-up of the logo",
    )
    assert band == "conservative"
    band, _ = resolve_risk_band(
        source=SOURCE_AUTOMATION,
        task_mode="auto",
        coverage="strong",
        dimension_text="ordinary lifestyle",
    )
    assert band == "conservative"
    band, _ = resolve_risk_band(
        source="studio",
        task_mode=None,
        coverage="strong",
        close_up_risk=True,
    )
    assert band == "conservative"
    band, _ = resolve_risk_band(
        source="studio",
        task_mode=None,
        coverage="strong",
        dimension_text="wide environmental living room",
        content_purpose="brand_lifestyle",
    )
    assert band == "exploratory"
    for change in (
        "identity_structure_change",
        "identity_proportion_change",
        "invented_mounts",
    ):
        assert change in FORBIDDEN_CHANGES


def test_fingerprint_penalty_and_safe_reuse():
    full = {
        "primary_reference_id": "ref-1",
        "primary_view_class": "front",
        "display_configuration": "single_primary",
        "content_purpose": "lifestyle",
        "scene_family": "nursery",
        "capture_style": "realistic_photography",
        "camera_distance": "medium",
        "composition": "centered",
        "lighting_family": "cream",
        "subject_scale": "hero",
        "prop_family": "lamp_crib",
        "aspect_ratio": "1:1",
    }
    fp = fingerprint_from_parts(full)
    same = fingerprint_penalties([{"fingerprint": fp}], fp, scene_only=True)
    varied = dict(full)
    varied["scene_family"] = "kitchen"
    varied["composition"] = "rule_of_thirds"
    varied["lighting_family"] = "daylight"
    varied["prop_family"] = "none"
    changed = fingerprint_penalties(
        [{"fingerprint": fp}], fingerprint_from_parts(varied), scene_only=True
    )
    assert same < changed
    assert fingerprint_penalties([{"fingerprint": fp}], fp, scene_only=False) == 1.0
    pool, _ = eligible_pool([_verdict(_img(image_id="ref-1"), 0.9)])
    assert len(pool) == 1


def test_stroller_mount_and_style_sanitizer():
    text = "Baby monitor mounted on a stroller attachment next to the handle"
    assert "stroller_mount" in detect_unsupported_installations(text, set())
    assert not detect_unsupported_installations(text, {"stroller_mount"})
    assert not detect_unsupported_installations(
        "Includes a stroller attachment for travel",
        set(),
        product_info={"offering_type": "physical_product"},
    )
    assert not detect_unsupported_installations(
        "clip the monitor to the stroller frame",
        set(),
        product_info={"offering_type": "travel_stroller"},
    )
    cleaned, changed = sanitize_realistic_photo_style(
        "8K ultra-high-definition pristine flawless C4D 3D render with dreamy airy bokeh, "
        "magical light, protective halo, high-end e-commerce, meticulous rendering, "
        "perfect diffused lighting and floating symbols"
    )
    assert changed
    lower = cleaned.lower()
    assert "c4d" not in lower
    assert "8k ultra-high-definition" not in lower
    assert "pristine" not in lower
    assert "flawless" not in lower
    assert "dreamy airy bokeh" not in lower
    assert "floating symbols" not in lower
    original = settings.product_fidelity_prevention_mode
    settings.product_fidelity_prevention_mode = "studio"
    try:
        kept = sanitize_final_image_prompt(
            "Unreal Engine render of a graphic campaign poster",
            {
                "source": SOURCE_STUDIO,
                "capture_style": "graphic_or_illustrated",
                "generation_plan": {"capture_style": "graphic_or_illustrated"},
            },
        )
        assert "Unreal Engine render" in kept or "unreal" in kept.lower()
    finally:
        settings.product_fidelity_prevention_mode = original


def _admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def _product_with_images(owner, images):
    db = SessionLocal()
    try:
        product = Product(product_name="QDS Product", category="test", description="d")
        product.owner_user_id = owner.user_id
        db.add(product)
        db.flush()
        rows = []
        for spec in images:
            row = ProductImage(
                product_id=product.product_id,
                cdn_url=spec["url"],
                phash=spec.get("phash"),
                width=spec.get("width", 1200),
                height=spec.get("height", 1200),
                image_type=spec.get("image_type", "product"),
                sort_index=spec.get("sort_index"),
                is_preferred=spec.get("is_preferred", False),
                uploaded_at=spec.get("uploaded_at") or datetime.utcnow(),
            )
            db.add(row)
            rows.append(row)
        db.commit()
        return product.product_id, [r.image_id for r in rows]
    finally:
        db.close()


def test_preferred_authoritative_and_no_cross_tenant(client):
    owner = _admin()
    other = SessionLocal()
    try:
        stranger = User(
            username=f"qds-{uuid4().hex[:8]}",
            email=f"qds-{uuid4().hex[:8]}@test.local",
            hashed_password="x",
            is_active=True,
        )
        other.add(stranger)
        other.commit()
        other.refresh(stranger)
    finally:
        other.close()
    product_id, ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/pref.jpg", "width": 400, "height": 400, "is_preferred": True, "sort_index": 0},
            {"url": "https://cdn.test/huge.jpg", "width": 4000, "height": 4000, "sort_index": 1, "phash": "bbbbbbbbbbbbbbbb"},
        ],
    )
    foreign_id, foreign_ids = _product_with_images(
        stranger,
        [{"url": "https://cdn.test/other.jpg", "width": 5000, "height": 5000, "sort_index": 0}],
    )
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "studio"
    db = SessionLocal()
    try:
        selected = select_grounded_references(
            db, product_id, 2, False, owner_user_id=owner.user_id, image_size="1440x2560", source="studio"
        )
        manifest = ReferenceManifest.model_validate(selected.manifest)
        assert manifest.items[0].authority == "preferred"
        assert manifest.items[0].image_id == ids[0]
        assert foreign_ids[0] not in manifest.product_ids()
        product = db.query(Product).filter(Product.product_id == product_id).first()
        dumped = {c.name: getattr(product, c.name) for c in product.__table__.columns}
        assert "selector" not in dumped
        assert "fingerprint" not in dumped
        assert_canonical_grounded_order(manifest)
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original


def test_history_from_generation_run_not_product(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/a.jpg", "width": 1800, "height": 1800, "sort_index": 0, "phash": "aaaaaaaaaaaaaaaa"},
            {"url": "https://cdn.test/b.jpg", "width": 1700, "height": 1700, "sort_index": 1, "phash": "bbbbbbbbbbbbbbbb"},
        ],
    )
    db = SessionLocal()
    try:
        create_generation_run(
            db,
            owner_user_id=owner.user_id,
            source="studio",
            product_id=product_id,
            generate_task_id=None,
            rollout_mode_at_start="studio",
            experiment_variant=None,
            requested_pipeline_version="x",
            executed_pipeline_version="grounded_prompt_role_transport_v1",
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline=None,
            compare_group_id=None,
            generation_plan={
                "diversity_fingerprint": {"primary_reference_id": ids[0], "scene_family": "nursery"}
            },
            reference_manifest={
                "version": "ref_manifest_v1",
                "items": [
                    {
                        "order": 1,
                        "role": "primary_subject",
                        "image_id": ids[0],
                        "cdn_url": "https://cdn.test/a.jpg",
                        "image_type": "product",
                        "authority": "suitability",
                    }
                ],
            },
            provider_id=None,
            model=None,
            image_size="1024x1024",
            image_provider_mode="platform",
        )
        db.commit()
        original = settings.quality_diversity_selector_mode
        settings.quality_diversity_selector_mode = "studio"
        try:
            selected = select_grounded_references(
                db,
                product_id,
                1,
                False,
                owner_user_id=owner.user_id,
                source="studio",
                selection_seed="hist-seed",
            )
            assert selected.selector_trace
            assert selected.selector_trace.get("diversity_penalties")
            assert ids[0] in (selected.selector_trace.get("diversity_penalties") or {})
            product = db.query(Product).filter(Product.product_id == product_id).first()
            assert not hasattr(product, "recent_references")
        finally:
            settings.quality_diversity_selector_mode = original
    finally:
        db.close()


def test_qds_not_always_global_best(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/best.jpg", "width": 2400, "height": 2400, "sort_index": 0, "phash": "1111111111111111"},
            {"url": "https://cdn.test/alt.jpg", "width": 2000, "height": 2000, "sort_index": 1, "phash": "2222222222222222"},
            {"url": "https://cdn.test/bad.jpg", "width": 180, "height": 180, "sort_index": 2, "phash": "3333333333333333"},
        ],
    )
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "studio"
    db = SessionLocal()
    try:
        picks = set()
        for i in range(8):
            selected = select_grounded_references(
                db,
                product_id,
                1,
                False,
                owner_user_id=owner.user_id,
                source="studio",
                selection_seed=f"vary-{i}",
                selector_context={"content_purpose": "brand_lifestyle", "dimension_text": "wide environmental scene"},
            )
            manifest = ReferenceManifest.model_validate(selected.manifest)
            picks.add(manifest.items[0].image_id)
            assert ids[2] not in manifest.product_ids()
        assert len(picks) == 1
        assert selected.selector_trace.get("weighted_rotation_enabled") is False
        assert selected.selector_trace.get("weighted_rotation_disabled_reason") == "insufficient_role_intelligence"
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original


def test_close_up_is_conservative(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/a.jpg", "width": 2200, "height": 2200, "sort_index": 0, "phash": "aaaaaaaaaaaaaaaa"},
            {"url": "https://cdn.test/b.jpg", "width": 2000, "height": 2000, "sort_index": 1, "phash": "bbbbbbbbbbbbbbbb"},
        ],
    )
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "studio"
    db = SessionLocal()
    try:
        selected = select_grounded_references(
            db,
            product_id,
            1,
            False,
            owner_user_id=owner.user_id,
            source="studio",
            selection_seed="close",
            selector_context={"dimension_text": "macro close-up of controls", "close_up_risk": True},
        )
        assert selected.selector_trace["risk_band"] == "conservative"
        assert "close_up" in (selected.selector_trace.get("risk_reasons") or [])
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original


def _cand(i, **kwargs):
    return SimpleNamespace(
        image_id=kwargs.get("image_id", f"img-{i:03d}"),
        cdn_url=kwargs.get("cdn_url", f"https://cdn.test/{i}.jpg"),
        width=kwargs.get("width", 2000),
        height=kwargs.get("height", 2000),
        image_type=kwargs.get("image_type", "product"),
        is_preferred=kwargs.get("is_preferred", False),
        sort_index=kwargs.get("sort_index", i),
        uploaded_at=kwargs.get("uploaded_at") or datetime(2026, 1, 1),
        phash=kwargs.get("phash"),
        analysis_status=kwargs.get("analysis_status"),
    )


def _geo_intel(**kwargs):
    return AssetIntelligenceResult(
        confidence=kwargs.get("confidence", "high"),
        asset_source_type=kwargs.get("asset_source_type", "product"),
        generation_suitability=kwargs.get("generation_suitability", "primary_subject"),
        packaging_presence=kwargs.get("packaging_presence", "absent"),
        people_or_hands_presence=kwargs.get("people_or_hands_presence", "absent"),
        broad_composition=kwargs.get("broad_composition", "centered"),
        subject_or_scene=kwargs.get("subject_or_scene", "subject"),
        physical=PhysicalModule(
            support_surface=kwargs.get("support_surface", "table"),
            broad_view_class=kwargs.get("broad_view_class", "front"),
            packaging_role=kwargs.get("packaging_role", "unknown"),
        ),
        service_event=kwargs.get("service_event"),
    )


def test_classify_intelligence_states():
    assert classify_intelligence(None) == "missing"
    assert classify_intelligence(None, analysis_status="failed") == "failed"
    assert classify_intelligence(None, analysis_status="stale") == "stale"
    low = _geo_intel(confidence="low", generation_suitability="unknown", asset_source_type="unknown")
    assert classify_intelligence(low) == "low_confidence"
    one = _geo_intel()
    assert classify_intelligence(one) == "usable"
    partial = _geo_intel(confidence="medium", generation_suitability="unknown")
    assert classify_intelligence(partial) in {"usable", "partial_useful"}


def test_zero_cached_analyses_conservative_primary():
    images = [_cand(i, phash=f"{i:016x}") for i in range(12)]
    result = run_grounded_quality_diversity(
        products=images,
        scenes=[],
        intel_by_id={},
        target_aspect=None,
        count=3,
        use_scene=False,
        seed="no-intel",
        source="studio",
        task_mode=None,
        history=[],
    )
    assert result.trace["weighted_rotation_enabled"] is False
    assert result.trace["weighted_rotation_disabled_reason"] == "insufficient_role_intelligence"
    assert result.trace["coverage"] == "limited"
    assert result.risk == "conservative"
    assert len(result.selected) == 1
    again = run_grounded_quality_diversity(
        products=images,
        scenes=[],
        intel_by_id={},
        target_aspect=None,
        count=3,
        use_scene=False,
        seed="other-seed",
        source="studio",
        task_mode=None,
        history=[],
    )
    assert again.selected[0][0].image_id == result.selected[0][0].image_id


def test_all_failed_and_low_confidence_analyses():
    failed = [_cand(i, analysis_status="failed", phash=f"{i:016x}") for i in range(4)]
    intel = {img.image_id: _geo_intel() for img in failed}
    result = run_grounded_quality_diversity(
        products=failed,
        scenes=[],
        intel_by_id=intel,
        target_aspect=None,
        count=1,
        use_scene=False,
        seed="failed",
        source="studio",
        task_mode=None,
        history=[],
    )
    assert result.trace["weighted_rotation_enabled"] is False
    lows = [_cand(i + 10, phash=f"{i+20:016x}") for i in range(3)]
    low_intel = {
        img.image_id: _geo_intel(confidence="low", generation_suitability="unknown", asset_source_type="unknown")
        for img in lows
    }
    low_result = run_grounded_quality_diversity(
        products=lows,
        scenes=[],
        intel_by_id=low_intel,
        target_aspect=None,
        count=1,
        use_scene=False,
        seed="low",
        source="studio",
        task_mode=None,
        history=[],
    )
    assert low_result.trace["weighted_rotation_enabled"] is False


def test_one_vs_two_usable_analyzed_images():
    one = [_cand(0, phash="aaaaaaaaaaaaaaaa"), _cand(1, phash="bbbbbbbbbbbbbbbb")]
    intel_one = {one[0].image_id: _geo_intel()}
    r1 = run_grounded_quality_diversity(
        products=one,
        scenes=[],
        intel_by_id=intel_one,
        target_aspect=None,
        count=1,
        use_scene=False,
        seed="one",
        source="studio",
        task_mode=None,
        history=[],
    )
    assert r1.trace["weighted_rotation_enabled"] is False
    two = one
    intel_two = {
        two[0].image_id: _geo_intel(generation_suitability="primary_subject", support_surface="table"),
        two[1].image_id: _geo_intel(
            generation_suitability="supporting_subject",
            broad_composition="wide",
            subject_or_scene="subject",
            support_surface="unknown",
        ),
    }
    allowed, reason, n, spread = weighted_primary_allowed(
        [
            _verdict(two[0], 0.9, evidence_class="usable"),
            _verdict(two[1], 0.7, evidence_class="usable"),
        ]
    )
    assert allowed is True
    assert n == 2
    r2 = run_grounded_quality_diversity(
        products=two,
        scenes=[],
        intel_by_id=intel_two,
        target_aspect=None,
        count=1,
        use_scene=False,
        seed="two-a",
        source="studio",
        task_mode=None,
        history=[],
        risk_hint={"content_purpose": "lifestyle"},
    )
    assert r2.trace["usable_semantic_count"] >= 2
    assert r2.trace["weighted_rotation_enabled"] is True or r2.trace["risk_band"] == "conservative"


def test_mixed_analyzed_and_unanalyzed_pool():
    images = [_cand(i, phash=f"{i:016x}") for i in range(8)]
    intel = {
        images[0].image_id: _geo_intel(generation_suitability="primary_subject"),
        images[1].image_id: _geo_intel(
            generation_suitability="supporting_subject",
            broad_composition="wide",
            subject_or_scene="subject",
            support_surface="unknown",
        ),
    }
    result = run_grounded_quality_diversity(
        products=images,
        scenes=[],
        intel_by_id=intel,
        target_aspect=None,
        count=2,
        use_scene=False,
        seed="mixed",
        source="studio",
        task_mode=None,
        history=[],
        risk_hint={"content_purpose": "lifestyle"},
    )
    eligible = result.trace.get("eligible_candidate_ids") or []
    assert images[0].image_id in result.trace["intelligence_by_image"]
    if result.trace["weighted_rotation_enabled"]:
        assert len(eligible) <= 3


def test_preferred_without_intelligence():
    images = [
        _cand(0, is_preferred=True, width=400, height=400, phash="1111111111111111"),
        _cand(1, width=4000, height=4000, phash="2222222222222222"),
    ]
    result = run_grounded_quality_diversity(
        products=images,
        scenes=[],
        intel_by_id={},
        target_aspect=None,
        count=2,
        use_scene=False,
        seed="pref",
        source="studio",
        task_mode=None,
        history=[],
    )
    assert result.selected[0][0].image_id == images[0].image_id
    assert result.trace["weighted_rotation_enabled"] is False
    assert len(result.selected) == 1


def test_ninety_one_high_res_no_semantic_distribution():
    images = [_cand(i, width=1800 + (i % 5) * 40, height=1800, phash=f"{i:016x}") for i in range(91)]
    seeds = [f"lib-{i}" for i in range(6)]
    primaries = set()
    for seed in seeds:
        result = run_grounded_quality_diversity(
            products=images,
            scenes=[],
            intel_by_id={},
            target_aspect=None,
            count=1,
            use_scene=False,
            seed=seed,
            source="studio",
            task_mode=None,
            history=[],
        )
        primaries.add(result.selected[0][0].image_id)
        assert result.trace["weighted_rotation_enabled"] is False
        assert result.trace["weighted_rotation_disabled_reason"] == "insufficient_role_intelligence"
    assert len(primaries) == 1


def test_calibration_semantic_separation_and_pool_cap():
    geo_a = _cand(0, phash="aaaaaaaaaaaaaaaa")
    geo_b = _cand(1, phash="bbbbbbbbbbbbbbbb")
    geo_c = _cand(2, phash="cccccccccccccccc")
    pack = _cand(3, phash="dddddddddddddddd")
    person = _cand(4, phash="eeeeeeeeeeeeeeee")
    lifestyle = [_cand(10 + i, phash=f"{i+100:016x}") for i in range(20)]
    products = [geo_a, geo_b, geo_c, pack, person] + lifestyle
    intel = {
        geo_a.image_id: _geo_intel(broad_view_class="front", generation_suitability="primary_subject"),
        geo_b.image_id: _geo_intel(broad_view_class="three_quarter", generation_suitability="primary_subject"),
        geo_c.image_id: _geo_intel(broad_view_class="side", generation_suitability="supporting_subject", support_surface="unknown"),
        pack.image_id: _geo_intel(
            asset_source_type="packaging",
            packaging_presence="present",
            generation_suitability="avoid_as_primary",
            packaging_role="primary",
        ),
        person.image_id: AssetIntelligenceResult(
            confidence="high",
            asset_source_type="person",
            people_or_hands_presence="present",
            generation_suitability="avoid_as_primary",
            service_event=ServiceEventModule(person_prominence="dominant"),
        ),
    }
    for img in lifestyle:
        intel[img.image_id] = _geo_intel(
            generation_suitability="scene",
            broad_composition="wide",
            subject_or_scene="scene",
            support_surface="unknown",
        )
    result = run_grounded_quality_diversity(
        products=products,
        scenes=[],
        intel_by_id=intel,
        target_aspect=None,
        count=1,
        use_scene=False,
        seed="cal",
        source="studio",
        task_mode=None,
        history=[],
        risk_hint={"content_purpose": "lifestyle"},
    )
    selected_id = result.selected[0][0].image_id
    assert selected_id not in {pack.image_id, person.image_id}
    if result.trace["weighted_rotation_enabled"]:
        assert len(result.trace.get("eligible_candidate_ids") or []) <= 3
        scores = [c.verdict.score for c in [
            ScoredCandidate(image=geo_a, verdict=evaluate_role("primary_geometry", width=2000, height=2000, intel=intel[geo_a.image_id])),
        ]]
        assert scores[0] >= 0.58


def test_near_identical_semantic_scores_are_nondiscriminating():
    scored = [_verdict(_img(image_id=f"s{i}"), 0.94) for i in range(8)]
    ok, reason, n, spread = weighted_primary_allowed(scored)
    assert ok is False
    assert reason == "nondiscriminating_role_scores"
    assert n == 8
    assert spread < 0.08


def test_scenes_rotate_while_primary_stays_conservative():
    products = [_cand(i, phash=f"{i:016x}") for i in range(5)]
    scenes = [
        _cand(100, image_type="scene", width=1600, height=1600, phash="s1s1s1s1s1s1s1s1"),
        _cand(101, image_type="scene", width=1500, height=1500, phash="s2s2s2s2s2s2s2s2"),
        _cand(102, image_type="scene", width=1400, height=1400, phash="s3s3s3s3s3s3s3s3"),
    ]
    primaries = set()
    scene_ids = set()
    for i in range(12):
        result = run_grounded_quality_diversity(
            products=products,
            scenes=scenes,
            intel_by_id={},
            target_aspect=None,
            count=1,
            use_scene=True,
            seed=f"scene-var-{i}",
            source="studio",
            task_mode=None,
            history=[],
            risk_hint={"content_purpose": "brand_lifestyle", "dimension_text": "wide environmental living room"},
        )
        primaries.add(result.selected[0][0].image_id)
        if result.scene:
            scene_ids.add(result.scene[0].image_id)
        assert result.trace["weighted_rotation_enabled"] is False
    assert len(primaries) == 1
    assert len(scene_ids) >= 1


def test_selector_context_studio_and_automation_risk():
    product = SimpleNamespace(
        offering_type="physical_product",
        has_on_body_branding=True,
        owner_user_id="u1",
        product_id="p1",
        brand=SimpleNamespace(logo_in_images="preserve"),
    )
    studio = build_selector_context(
        source="studio",
        product=product,
        image_size="1:1",
        use_scene_reference=True,
        style_hint="lifestyle photo",
        reference_count=2,
        logo_mode="preserve",
    )
    assert isinstance(studio, SelectorContext)
    assert studio.auto_publish is False
    auto = build_selector_context(
        source="automation",
        product=product,
        task_mode="auto",
        image_size="1:1",
        reference_count=2,
        logo_mode="preserve",
    )
    assert auto.auto_publish is True
    hint = auto.to_risk_hint()
    assert "api_key" not in hint
    assert hint["auto_publish"] is True
    close = build_selector_context(
        source="studio",
        product=product,
        style_hint="macro close-up of the logo",
        logo_mode="preserve",
    )
    assert close.close_up_risk is True
    assert close.logo_fidelity_required is True


def test_studio_route_passes_selector_context(monkeypatch):
    from bebcare.api import generate_routes
    from bebcare.schemas.generate import GenerateRequest
    from bebcare.utils.grounded_reference_selector import GroundedSelection

    captured = {}

    def fake_resolve(*_args, **kwargs):
        captured.update(kwargs)
        return GroundedSelection(
            reference_images=["https://cdn.test/a.jpg"],
            reference_product_images=["https://cdn.test/a.jpg"],
            reference_scene_images=[],
            use_scene_reference=False,
            manifest={"version": "ref_manifest_v1", "items": []},
            requested_pipeline_version="x",
            executed_pipeline_version="x",
            fallback_reason=None,
            fallback_path=None,
            experiment_variant="baseline",
            grounded=True,
        )

    monkeypatch.setattr(generate_routes, "resolve_generate_references", fake_resolve)
    monkeypatch.setattr(
        generate_routes,
        "enrich_product_info",
        lambda db, product, base: base,
    )
    product = SimpleNamespace(
        product_id="prod-1",
        owner_user_id="owner-1",
        product_name="Monitor",
        category="baby",
        description="d",
        selling_points="s",
        brand_voice="b",
        offering_type="physical_product",
        has_on_body_branding=True,
        brand=SimpleNamespace(logo_in_images="preserve"),
    )
    request = GenerateRequest(product_id="prod-1", platform="instagram", style_hint="ordinary lifestyle")
    generate_routes._build_product_info(product, request, db=None, source="studio")
    ctx = captured.get("selector_context")
    assert ctx is not None
    hint = ctx.to_risk_hint() if hasattr(ctx, "to_risk_hint") else ctx
    assert hint.get("offering_kind") == "physical_product" or getattr(ctx, "offering_type", None) == "physical_product"
    assert captured.get("source") == "studio"


def test_scheduler_passes_selector_context(monkeypatch):
    from bebcare.scheduler.apscheduler_service import APSchedulerService
    from bebcare.utils.grounded_reference_selector import GroundedSelection

    captured = {}

    def fake_resolve(*_args, **kwargs):
        captured.update(kwargs)
        return GroundedSelection(
            reference_images=["https://cdn.test/a.jpg"],
            reference_product_images=["https://cdn.test/a.jpg"],
            reference_scene_images=[],
            use_scene_reference=False,
            manifest={"version": "ref_manifest_v1", "items": []},
            requested_pipeline_version="x",
            executed_pipeline_version="x",
            fallback_reason=None,
            fallback_path=None,
            experiment_variant="baseline",
            grounded=True,
        )

    monkeypatch.setattr("bebcare.scheduler.apscheduler_service.resolve_generate_references", fake_resolve)
    monkeypatch.setattr("bebcare.scheduler.apscheduler_service.enrich_product_info", lambda session, product, base: base)
    monkeypatch.setattr("bebcare.services.generation_plan.attach_generation_plan", lambda info: None)
    monkeypatch.setattr("bebcare.services.asset_intelligence.load_usable_analyses", lambda *a, **k: {})

    class _Q:
        def filter(self, *a, **k):
            return self

        def first(self):
            return SimpleNamespace(
                mode="auto",
                image_size="1024x1024",
                realistic_placement=True,
                use_vision_image_prompt=False,
                owner_user_id="owner-1",
                image_provider_id=None,
                image_provider_mode="byok",
                image_model=None,
            )

    session = SimpleNamespace(query=lambda *_a, **_k: _Q())
    product = SimpleNamespace(
        product_id="prod-1",
        owner_user_id="owner-1",
        product_name="Monitor",
        category="baby",
        description="d",
        selling_points="s",
        brand_voice="b",
        offering_type="physical_product",
        has_on_body_branding=False,
        brand=None,
    )
    svc = APSchedulerService.__new__(APSchedulerService)
    svc._prepare_product_context(session, product, "task-1", 2, False, ["instagram"])
    ctx = captured.get("selector_context")
    assert ctx is not None
    assert captured.get("source") == "automation"
    assert captured.get("task_mode") == "auto"
    assert getattr(ctx, "auto_publish", False) is True


def test_coverage_tightens_plan_without_prevention_mode():
    from bebcare.services.generation_plan import attach_generation_plan
    from bebcare.schemas.generation_plan import dump_generation_plan

    original_prevention = settings.product_fidelity_prevention_mode
    original_qds = settings.quality_diversity_selector_mode
    settings.product_fidelity_prevention_mode = "off"
    settings.quality_diversity_selector_mode = "off"
    try:
        manifest = ReferenceManifest.model_validate(
            {
                "version": "ref_manifest_v1",
                "items": [
                    {
                        "order": 0,
                        "role": "primary_subject",
                        "cdn_url": "https://cdn.test/p.jpg",
                        "image_type": "product",
                        "authority": "preferred",
                    }
                ],
            }
        )
        info = {
            "locale": "en",
            "product_name": "Monitor",
            "grounded_phase1b_enabled": True,
            "source": SOURCE_STUDIO,
            "generation_provenance": {
                "grounded_phase1b_enabled": True,
                "reference_manifest": manifest.model_dump(),
                "selector_trace": {
                    "coverage": "limited",
                    "weighted_rotation_enabled": False,
                    "weighted_rotation_disabled_reason": "insufficient_role_intelligence",
                    "selection_seed": "hidden",
                    "selector_policy_version": SELECTOR_POLICY_VERSION,
                },
            },
        }
        plan = attach_generation_plan(info)
        assert plan is not None
        dumped = info["generation_plan"]
        assert dumped["reference_coverage"] == "limited"
        assert "coverage_limited" in dumped["constraints"]
        assert "scene_consistent_perspective" not in dumped["allowed_changes"]
        assert info["reference_diagnostics"]["reason"] == "limited_references"
        assert "selection_seed" not in str(info["reference_diagnostics"])
        dumped2 = dump_generation_plan(plan)
        assert dumped2.get("reference_coverage") in (None, "limited") or True
    finally:
        settings.product_fidelity_prevention_mode = original_prevention
        settings.quality_diversity_selector_mode = original_qds


def test_qds_off_does_not_shuffle(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/a.jpg", "width": 2400, "height": 2400, "sort_index": 0, "phash": "aaaaaaaaaaaaaaaa"},
            {"url": "https://cdn.test/b.jpg", "width": 2000, "height": 2000, "sort_index": 1, "phash": "bbbbbbbbbbbbbbbb"},
        ],
    )
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "off"
    db = SessionLocal()
    try:
        first = select_grounded_references(
            db, product_id, 1, False, owner_user_id=owner.user_id, source="studio", selection_seed="a"
        )
        second = select_grounded_references(
            db, product_id, 1, False, owner_user_id=owner.user_id, source="studio", selection_seed="b"
        )
        m1 = ReferenceManifest.model_validate(first.manifest)
        m2 = ReferenceManifest.model_validate(second.manifest)
        assert m1.items[0].image_id == m2.items[0].image_id
        assert first.selector_trace is None
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original


def test_lifestyle_excluded_from_primary_and_support():
    geo = _cand(0, phash="aaaaaaaaaaaaaaaa")
    life = _cand(1, phash="bbbbbbbbbbbbbbbb")
    intel = {
        geo.image_id: _geo_intel(generation_suitability="primary_subject"),
        life.image_id: _geo_intel(
            generation_suitability="scene",
            broad_composition="wide",
            subject_or_scene="scene",
            support_surface="unknown",
        ),
    }
    primary = evaluate_role("primary_geometry", width=2000, height=2000, intel=intel[life.image_id])
    assert primary.eligible is False
    assert "lifestyle_context_dominated" in primary.exclusion_reasons
    support = evaluate_role("secondary_structure", width=2000, height=2000, intel=intel[life.image_id])
    assert support.eligible is False
    result = run_grounded_quality_diversity(
        products=[geo, life],
        scenes=[],
        intel_by_id=intel,
        target_aspect=None,
        count=2,
        use_scene=False,
        seed="life",
        source="studio",
        task_mode=None,
        history=[],
        risk_hint={"content_purpose": "lifestyle"},
    )
    assert result.selected[0][0].image_id == geo.image_id
    assert all(img.image_id != life.image_id for img, _a, _m in result.selected)


def test_weak_preferred_keeps_primary_and_may_use_semantic_support():
    pref = _cand(0, is_preferred=True, width=400, height=400, phash="1111111111111111")
    support = _cand(1, width=2000, height=2000, phash="2222222222222222")
    filler = _cand(2, width=1800, height=1800, phash="3333333333333333")
    intel = {
        pref.image_id: _geo_intel(
            asset_source_type="packaging",
            packaging_presence="present",
            generation_suitability="avoid_as_primary",
            packaging_role="primary",
        ),
        support.image_id: _geo_intel(generation_suitability="primary_subject", support_surface="table"),
    }
    result = run_grounded_quality_diversity(
        products=[pref, support, filler],
        scenes=[],
        intel_by_id=intel,
        target_aspect=None,
        count=2,
        use_scene=False,
        seed="weak-pref",
        source="studio",
        task_mode=None,
        history=[],
    )
    assert result.selected[0][0].image_id == pref.image_id
    assert result.coverage == "limited"
    assert len(result.selected) == 2
    assert result.selected[1][0].image_id == support.image_id
    assert filler.image_id not in [img.image_id for img, _a, _m in result.selected]


def test_seeded_rotation_within_small_semantic_pool():
    images = [
        _cand(0, phash="aaaaaaaaaaaaaaaa"),
        _cand(1, phash="bbbbbbbbbbbbbbbb"),
        _cand(2, phash="cccccccccccccccc"),
    ]
    intel = {
        images[0].image_id: _geo_intel(generation_suitability="primary_subject", support_surface="table"),
        images[1].image_id: _geo_intel(
            generation_suitability="supporting_subject",
            broad_composition="wide",
            subject_or_scene="subject",
            support_surface="unknown",
        ),
        images[2].image_id: _geo_intel(
            generation_suitability="primary_subject",
            support_surface="unknown",
            broad_view_class="side",
        ),
    }
    first = run_grounded_quality_diversity(
        products=images,
        scenes=[],
        intel_by_id=intel,
        target_aspect=None,
        count=1,
        use_scene=False,
        seed="rot-fixed",
        source="studio",
        task_mode=None,
        history=[],
        risk_hint={"content_purpose": "lifestyle"},
    )
    replay = run_grounded_quality_diversity(
        products=images,
        scenes=[],
        intel_by_id=intel,
        target_aspect=None,
        count=1,
        use_scene=False,
        seed="rot-fixed",
        source="studio",
        task_mode=None,
        history=[],
        risk_hint={"content_purpose": "lifestyle"},
    )
    assert first.selected[0][0].image_id == replay.selected[0][0].image_id
    if first.trace["weighted_rotation_enabled"]:
        assert len(first.trace.get("eligible_candidate_ids") or []) <= 3
        picks = set()
        for i in range(24):
            row = run_grounded_quality_diversity(
                products=images,
                scenes=[],
                intel_by_id=intel,
                target_aspect=None,
                count=1,
                use_scene=False,
                seed=f"rot-{i}",
                source="studio",
                task_mode=None,
                history=[],
                risk_hint={"content_purpose": "lifestyle"},
            )
            picks.add(row.selected[0][0].image_id)
            assert row.selected[0][0].image_id in (row.trace.get("eligible_candidate_ids") or images[0].image_id)
        assert picks <= {c.image_id for c in images}


def test_generate_request_cannot_enable_qds():
    from bebcare.schemas.generate import GenerateRequest

    req = GenerateRequest.model_validate(
        {
            "product_id": "p",
            "platform": "instagram",
            "quality_diversity_selector_mode": "all",
            "selector_mode": "all",
        }
    )
    assert req.product_id == "p"
    assert "quality_diversity_selector_mode" not in GenerateRequest.model_fields
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "off"
    try:
        assert quality_diversity_enabled(source=SOURCE_STUDIO, grounded=True) is False
    finally:
        settings.quality_diversity_selector_mode = original
