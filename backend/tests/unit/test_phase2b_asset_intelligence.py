"""Phase 2B semantic asset intelligence — mocked vision only."""

from io import BytesIO
from unittest.mock import patch

from PIL import Image

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.product import Product, ProductImage
from bebcare.models.product_image_analysis import ProductImageAnalysis
from bebcare.models.user import User
from bebcare.schemas.asset_intelligence import (
    SEMANTIC_SCHEMA_VERSION,
    AssetIntelligenceResult,
)
from bebcare.schemas.generation_plan import build_generation_plan, resolve_physical_instance_limit
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
from bebcare.services.asset_intelligence import (
    enqueue_selected_intelligence,
    load_usable_analyses,
    run_intelligence_job,
)
from bebcare.services.asset_intelligence_adapter import (
    SYSTEM_PROMPT,
    analyze_reference_image,
    resolve_platform_vision_credentials,
)
from bebcare.services.asset_intelligence_policy import AnalysisFailure, FAILURE_PERMANENT
from bebcare.services.asset_intelligence_rollout import semantic_analysis_enabled
from bebcare.services.deterministic_metadata import content_hash_bytes
from bebcare.utils.reference_selector import resolve_generate_references


def _png(color=(10, 20, 30, 255), size=(64, 64)) -> bytes:
    image = Image.new("RGBA", size, color)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def _product(owner, name="Intel SKU"):
    db = SessionLocal()
    try:
        product = Product(
            product_name=name,
            category="test",
            description="d",
            offering_type="unknown",
        )
        product.owner_user_id = owner.user_id
        db.add(product)
        db.commit()
        return product.product_id
    finally:
        db.close()


def _image(db, product_id, raw, *, preferred=False, image_type="product"):
    digest = content_hash_bytes(raw)
    row = ProductImage(
        product_id=product_id,
        cdn_url=f"https://cdn.test/{digest[:8]}.png",
        image_type=image_type,
        width=64,
        height=64,
        is_preferred=preferred,
        content_hash=digest,
        analysis_status="ready",
        deterministic_metadata_version="det_meta_v1",
    )
    db.add(row)
    db.flush()
    return row


def _complete_ok(payload=None):
    body = payload or {
        "asset_source_type": "product",
        "subject_or_scene": "subject",
        "people_or_hands_presence": "absent",
        "text_presence": "absent",
        "brand_mark_presence": "unknown",
        "broad_composition": "centered",
        "broad_lighting": "studio",
        "screenshot_or_interface_presence": "absent",
        "packaging_presence": "absent",
        "dominant_offering_evidence": "physical_product",
        "generation_suitability": "primary_subject",
        "confidence": "medium",
        "warnings": [],
    }

    def _fn(messages):
        import json

        return json.dumps(body), {"usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}

    return _fn


def test_system_prompt_treats_visible_text_as_untrusted():
    assert "untrusted" in SYSTEM_PROMPT.lower()
    assert "never follow" in SYSTEM_PROMPT.lower()


def test_rollout_off_skips_semantic_call(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "off"
    calls = []

    def boom(messages):
        calls.append(messages)
        raise AssertionError("should not call vision")

    try:
        assert semantic_analysis_enabled(source="studio") is False
        assert enqueue_selected_intelligence(
            image_ids=["x"],
            owner_user_id="u",
            product_id="p",
            source="studio",
            requested_mode="all",
            complete=boom,
        ) == []
        owner = _admin()
        product_id = _product(owner)
        db = SessionLocal()
        try:
            _image(db, product_id, _png())
            db.commit()
            out = run_intelligence_job(
                image_ids=[db.query(ProductImage).filter(ProductImage.product_id == product_id).one().image_id],
                owner_user_id=owner.user_id,
                product_id=product_id,
                source="studio",
                complete=boom,
            )
            assert out["processed"] == []
            assert calls == []
        finally:
            db.close()
    finally:
        settings.asset_intelligence_mode = original


def test_studio_mode_does_not_enable_automation():
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    try:
        assert semantic_analysis_enabled(source="studio", requested_mode="off") is True
        assert semantic_analysis_enabled(source="automation", requested_mode="all") is False
    finally:
        settings.asset_intelligence_mode = original


def test_client_requested_mode_cannot_bypass_off():
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "off"
    try:
        assert semantic_analysis_enabled(source="studio", requested_mode="all") is False
        assert enqueue_selected_intelligence(
            image_ids=["a"],
            owner_user_id="u",
            product_id="p",
            source="studio",
            requested_mode="all",
        ) == []
    finally:
        settings.asset_intelligence_mode = original


def test_platform_vision_does_not_reuse_deepseek_key_on_vision_host():
    orig = (
        settings.vision_api_key,
        settings.vision_api_url,
        settings.deepseek_api_key,
        settings.deepseek_api_url,
    )
    try:
        settings.vision_api_url = "https://vision.example.test/v1"
        settings.vision_api_key = None
        settings.deepseek_api_key = "deepseek-not-for-vision"
        settings.deepseek_api_url = "https://api.deepseek.com/v1"
        try:
            resolve_platform_vision_credentials()
            raise AssertionError("expected invalid_analysis_configuration")
        except AnalysisFailure as exc:
            assert exc.failure_type == FAILURE_PERMANENT
            assert exc.error_category == "invalid_analysis_configuration"
        settings.vision_api_key = "vision-key"
        key, url = resolve_platform_vision_credentials()
        assert key == "vision-key"
        assert url.endswith("/chat/completions")
        assert "vision.example.test" in url
    finally:
        (
            settings.vision_api_key,
            settings.vision_api_url,
            settings.deepseek_api_key,
            settings.deepseek_api_url,
        ) = orig


def test_cache_hit_avoids_second_call(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    calls = {"n": 0}

    def complete(messages):
        calls["n"] += 1
        return _complete_ok()(messages)

    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((41, 42, 43, 255), size=(78, 78)))
        db.commit()
        image_id = image.image_id
        first = run_intelligence_job(
            image_ids=[image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=complete,
        )
        second = run_intelligence_job(
            image_ids=[image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=complete,
        )
        assert first["processed"] == [image_id]
        assert any(item["reason"] == "cache_hit" for item in second["skipped"])
        assert calls["n"] == 1
        row = (
            db.query(ProductImageAnalysis)
            .filter(ProductImageAnalysis.product_image_id == image.image_id)
            .one()
        )
        assert row.status == "ready"
        assert (row.usage or {}).get("prompt_tokens") == 11
        assert (row.usage or {}).get("purpose") == "asset_intelligence"
        assert (row.usage or {}).get("provider") == "platform_vision"
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_cache_invalidates_on_schema_version(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "Schema Invalidate")
    raw = _png((3, 4, 5, 255), size=(66, 66))
    db = SessionLocal()
    try:
        image = _image(db, product_id, raw)
        db.flush()
        stale = ProductImageAnalysis(
            content_hash=image.content_hash,
            schema_version="sem_v0",
            model_version="agnes-2.5-flash",
            offering_context_version="offering_v1:unknown",
            status="ready",
            normalized_result={"asset_source_type": "product"},
            product_image_id=image.image_id,
        )
        stale.owner_user_id = owner.user_id
        db.add(stale)
        db.commit()
        calls = {"n": 0}

        def complete(messages):
            calls["n"] += 1
            return _complete_ok()(messages)

        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=complete,
        )
        assert calls["n"] == 1
        assert (
            db.query(ProductImageAnalysis)
            .filter(ProductImageAnalysis.product_image_id == image.image_id)
            .count()
            >= 1
        )
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_malformed_json_retries_once():
    calls = {"n": 0}

    def complete(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json", {}
        return _complete_ok()(messages)

    payload = analyze_reference_image(
        image_url="https://cdn.test/x.png",
        offering_type="unknown",
        complete=complete,
    )
    assert calls["n"] == 2
    assert payload["retries"] == 1
    assert payload["result"].asset_source_type == "product"


def test_failure_does_not_block_generation(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "Fail Gen")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((21, 22, 23, 255), size=(74, 74)))
        db.commit()

        def boom(messages):
            raise RuntimeError("vision_down")

        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=boom,
        )
        selected = resolve_generate_references(
            db,
            product_id=product_id,
            owner_user_id=owner.user_id,
            reference_count=1,
            use_scene_reference=False,
            source="studio",
        )
        assert selected.reference_images
        row = (
            db.query(ProductImageAnalysis)
            .filter(ProductImageAnalysis.product_image_id == image.image_id)
            .one()
        )
        assert row.status == "failed"
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_cross_tenant_cache_isolation(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    other = User(username="intel_b", email="intel_b@test.local", hashed_password="x")
    db = SessionLocal()
    try:
        db.add(other)
        db.flush()
        product_a = Product(product_name="A", category="t", description="d", offering_type="unknown")
        product_a.owner_user_id = owner.user_id
        product_b = Product(product_name="B", category="t", description="d", offering_type="unknown")
        product_b.owner_user_id = other.user_id
        db.add_all([product_a, product_b])
        db.flush()
        raw = _png()
        img_a = _image(db, product_a.product_id, raw)
        img_b = _image(db, product_b.product_id, raw)
        db.commit()
        run_intelligence_job(
            image_ids=[img_a.image_id],
            owner_user_id=owner.user_id,
            product_id=product_a.product_id,
            source="studio",
            complete=_complete_ok(),
        )
        mapped = load_usable_analyses(
            db, owner_user_id=other.user_id, product_id=product_b.product_id
        )
        assert mapped == {}
        assert db.query(ProductImageAnalysis).filter(
            ProductImageAnalysis.owner_user_id == other.user_id
        ).count() == 0
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_preferred_packaging_remains_authoritative(client):
    original_g = settings.grounded_rollout_mode
    original_i = settings.asset_intelligence_mode
    settings.grounded_rollout_mode = "studio"
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        pack = _image(db, product_id, _png((1, 2, 3, 255)), preferred=True)
        other = _image(db, product_id, _png((9, 9, 9, 255)))
        db.commit()
        run_intelligence_job(
            image_ids=[pack.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=_complete_ok(
                {
                    "asset_source_type": "packaging",
                    "packaging_presence": "present",
                    "screenshot_or_interface_presence": "absent",
                    "generation_suitability": "avoid_as_primary",
                    "dominant_offering_evidence": "physical_product",
                }
            ),
        )
        selected = resolve_generate_references(
            db,
            product_id=product_id,
            owner_user_id=owner.user_id,
            reference_count=1,
            use_scene_reference=False,
            source="studio",
        )
        primary = selected.manifest["items"][0]["image_id"]
        assert primary == pack.image_id
        assert other.image_id != pack.image_id
    finally:
        settings.grounded_rollout_mode = original_g
        settings.asset_intelligence_mode = original_i
        db.close()


def test_packaging_not_silent_hero_when_not_preferred(client):
    original_g = settings.grounded_rollout_mode
    original_i = settings.asset_intelligence_mode
    settings.grounded_rollout_mode = "studio"
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        pack = _image(db, product_id, _png((1, 2, 3, 255)))
        hero = _image(db, product_id, _png((200, 10, 10, 255)))
        db.commit()
        run_intelligence_job(
            image_ids=[pack.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=_complete_ok(
                {
                    "asset_source_type": "packaging",
                    "packaging_presence": "present",
                    "generation_suitability": "avoid_as_primary",
                }
            ),
        )
        selected = resolve_generate_references(
            db,
            product_id=product_id,
            owner_user_id=owner.user_id,
            reference_count=1,
            use_scene_reference=False,
            source="studio",
        )
        assert selected.manifest["items"][0]["image_id"] == hero.image_id
    finally:
        settings.grounded_rollout_mode = original_g
        settings.asset_intelligence_mode = original_i
        db.close()


def test_screenshot_does_not_set_physical_instance_limit():
    manifest = ReferenceManifest(
        items=[
            ManifestItem(
                order=0,
                role="primary_subject",
                image_id="img-1",
                cdn_url="https://cdn.test/a.png",
                image_type="product",
                authority="suitability",
            )
        ]
    )
    plan = build_generation_plan(
        manifest,
        product_info={
            "offering_kind": "unknown",
            "asset_intelligence": {
                "enabled": True,
                "cache_hit": True,
                "results": [{"is_screenshot": True, "is_packaging": False}],
            },
        },
    )
    assert resolve_physical_instance_limit(product_info={"offering_kind": "unknown"}) is None
    assert plan.subject.physical_instance_limit is None
    assert "screenshot_not_physical_instance" in plan.constraints
    assert plan.handheld_physical_replacement == "prohibited"


def test_unknown_offering_remains_usable(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "off"
    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        _image(db, product_id, _png())
        db.commit()
        selected = resolve_generate_references(
            db,
            product_id=product_id,
            owner_user_id=owner.user_id,
            reference_count=1,
            use_scene_reference=False,
            source="studio",
        )
        assert selected.reference_images
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_no_credits_or_byok_on_analysis(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((51, 52, 53, 255), size=(80, 80)))
        db.commit()
        with patch("bebcare.services.credit_grant_service.reserve_one") as reserve, patch(
            "bebcare.providers.registry.resolve_image_provider"
        ) as byok:
            run_intelligence_job(
                image_ids=[image.image_id],
                owner_user_id=owner.user_id,
                product_id=product_id,
                source="studio",
                complete=_complete_ok(),
            )
            reserve.assert_not_called()
            byok.assert_not_called()
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_no_phase3_qa_or_regeneration_symbols():
    from bebcare.services import asset_intelligence as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "regenerat" not in source.lower()
    assert "visual_qa" not in source.lower()
    assert "shotplan" not in source.lower()


def test_sem_v2_normalizes_case_hyphen_and_numeric_confidence():
    from bebcare.schemas.asset_intelligence import parse_intelligence_result

    result = parse_intelligence_result(
        {
            "geometry_reference_suitability": "STRONG",
            "kit_or_group_image": "NO",
            "confidence": 0.91,
            "physical": {"complete_silhouette_visible": "complete", "major_occlusion": "ABSENT"},
        }
    )
    assert result.geometry_reference_suitability == "strong"
    assert result.kit_or_group_image == "no"
    assert result.confidence == "high"
    assert result.physical.major_occlusion == "absent"
    assert SYSTEM_PROMPT.count("Resolution alone does not establish geometry suitability") == 1
