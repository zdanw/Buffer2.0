"""Isolated QDS E2E against real selector services. No provider calls."""

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.product import Product, ProductImage
from bebcare.models.user import User
from bebcare.schemas.asset_intelligence import AssetIntelligenceResult, PhysicalModule
from bebcare.schemas.reference_manifest import ReferenceManifest
from bebcare.services.generation_plan import attach_generation_plan
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO, selection_provenance
from bebcare.services.quality_diversity_context import build_selector_context
from bebcare.services.quality_diversity_policy import SELECTOR_POLICY_VERSION
from bebcare.utils.grounded_reference_selector import select_grounded_references
from bebcare.utils.reference_selector import resolve_generate_references


def _admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def _cleanup(product_id: str):
    db = SessionLocal()
    try:
        db.query(ProductImage).filter(ProductImage.product_id == product_id).delete()
        db.query(Product).filter(Product.product_id == product_id).delete()
        db.commit()
    finally:
        db.close()


def _seed_product(owner, *, preferred=False, extra=2):
    db = SessionLocal()
    try:
        product = Product(
            product_name=f"QDS E2E {uuid4().hex[:8]}",
            category="test",
            description="isolated qds e2e",
            offering_type="physical_product",
        )
        product.owner_user_id = owner.user_id
        db.add(product)
        db.flush()
        rows = []
        hashes = [
            "aaaaaaaaaaaaaaaa",
            "5555555555555555",
            "f0f0f0f0f0f0f0f0",
            "0f0f0f0f0f0f0f0f",
            "3333333333333333",
        ]
        for index in range(extra + 1):
            row = ProductImage(
                product_id=product.product_id,
                cdn_url=f"https://cdn.test/qds-e2e-{index}.jpg",
                phash=hashes[index % len(hashes)],
                width=1600 + index * 200,
                height=1600,
                image_type="product",
                sort_index=index,
                is_preferred=bool(preferred and index == 0),
                uploaded_at=datetime.utcnow(),
            )
            db.add(row)
            rows.append(row)
        scene = ProductImage(
            product_id=product.product_id,
            cdn_url="https://cdn.test/qds-e2e-scene.jpg",
            phash="ffffffffffffffff",
            width=1600,
            height=900,
            image_type="scene",
            sort_index=90,
            uploaded_at=datetime.utcnow(),
        )
        db.add(scene)
        db.commit()
        return product.product_id, [r.image_id for r in rows], scene.image_id, str(product.owner_user_id)
    finally:
        db.close()


def _intel(view="front"):
    return AssetIntelligenceResult(
        confidence="high",
        asset_source_type="product",
        generation_suitability="primary_subject",
        packaging_presence="absent",
        people_or_hands_presence="absent",
        broad_composition="centered",
        subject_or_scene="subject",
        physical=PhysicalModule(support_surface="table", broad_view_class=view),
    )


def test_e2e_no_intelligence_studio_and_automation(client):
    owner = _admin()
    product_id, ids, scene_id, owner_id = _seed_product(owner, preferred=True, extra=3)
    original = settings.quality_diversity_selector_mode
    original_prevention = settings.product_fidelity_prevention_mode
    settings.quality_diversity_selector_mode = "all"
    settings.product_fidelity_prevention_mode = "off"
    db = SessionLocal()
    try:
        studio_ctx = build_selector_context(
            source=SOURCE_STUDIO,
            product=SimpleNamespace(
                offering_type="physical_product",
                has_on_body_branding=False,
                owner_user_id=owner_id,
                product_id=product_id,
                brand=None,
            ),
            image_size="1024x1024",
            use_scene_reference=True,
            style_hint="ordinary lifestyle",
            reference_count=2,
        )
        auto_ctx = build_selector_context(
            source=SOURCE_AUTOMATION,
            product=SimpleNamespace(
                offering_type="physical_product",
                has_on_body_branding=False,
                owner_user_id=owner_id,
                product_id=product_id,
                brand=None,
            ),
            task_mode="auto",
            image_size="1024x1024",
            reference_count=2,
        )
        assert auto_ctx.auto_publish is True
        a = select_grounded_references(
            db,
            product_id,
            2,
            True,
            owner_user_id=owner_id,
            source="studio",
            selection_seed="e2e-a",
            selector_context=studio_ctx,
        )
        b = select_grounded_references(
            db,
            product_id,
            2,
            True,
            owner_user_id=owner_id,
            source="studio",
            selection_seed="e2e-b",
            selector_context=studio_ctx,
        )
        auto = select_grounded_references(
            db,
            product_id,
            2,
            False,
            owner_user_id=owner_id,
            source="automation",
            task_mode="auto",
            selection_seed="e2e-auto",
            selector_context=auto_ctx,
        )
        ma = ReferenceManifest.model_validate(a.manifest)
        mb = ReferenceManifest.model_validate(b.manifest)
        assert ma.items[0].image_id == ids[0]
        assert ma.items[0].image_id == mb.items[0].image_id
        assert a.selector_trace["weighted_rotation_enabled"] is False
        assert a.selector_trace["weighted_rotation_disabled_reason"] == "insufficient_role_intelligence"
        assert a.selector_trace["risk_band"] == "conservative"
        assert auto.selector_trace["risk_band"] == "conservative"
        assert "auto_publish" in (auto.selector_trace.get("risk_reasons") or [])
        assert scene_id in (ma.scene_ids() if hasattr(ma, "scene_ids") else [i.image_id for i in ma.items if i.role == "scene"] or [])
        product_ids = [i.image_id for i in ma.items if i.image_type == "product"]
        assert product_ids == [ids[0]]
        info = {
            "locale": "en",
            "product_name": "E2E",
            "grounded_phase1b_enabled": True,
            "generation_provenance": selection_provenance(a, source="studio"),
        }
        attach_generation_plan(info)
        diag = info.get("reference_diagnostics") or {}
        assert set(diag.keys()) <= {"coverage", "reason", "diversity_applied"}
        assert "selection_seed" not in diag
        assert info["generation_plan"]["reference_coverage"] == "limited"
        assert "coverage_limited" in info["generation_plan"]["constraints"]
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original
        settings.product_fidelity_prevention_mode = original_prevention
        _cleanup(product_id)


def test_e2e_mocked_analysis_seed_replay_and_route_context(client):
    owner = _admin()
    product_id, ids, _scene_id, owner_id = _seed_product(owner, preferred=False, extra=2)
    original = settings.quality_diversity_selector_mode
    grounded_original = settings.grounded_rollout_mode
    settings.quality_diversity_selector_mode = "studio"
    intel = {
        ids[0]: _intel("front"),
        ids[1]: AssetIntelligenceResult(
            confidence="high",
            asset_source_type="product",
            generation_suitability="supporting_subject",
            packaging_presence="absent",
            people_or_hands_presence="absent",
            broad_composition="wide",
            subject_or_scene="subject",
            physical=PhysicalModule(support_surface="unknown", broad_view_class="side"),
        ),
        ids[2]: _intel("three_quarter"),
    }
    db = SessionLocal()
    try:
        ctx = build_selector_context(
            source=SOURCE_STUDIO,
            product=SimpleNamespace(
                offering_type="physical_product",
                has_on_body_branding=False,
                owner_user_id=owner_id,
                product_id=product_id,
                brand=None,
            ),
            style_hint="ordinary lifestyle photograph",
            reference_count=1,
        )
        first = select_grounded_references(
            db,
            product_id,
            1,
            False,
            owner_user_id=owner_id,
            source="studio",
            selection_seed="e2e-replay",
            selector_context=ctx,
            intelligence_by_image=intel,
        )
        replay = select_grounded_references(
            db,
            product_id,
            1,
            False,
            owner_user_id=owner_id,
            source="studio",
            selection_seed="e2e-replay",
            selector_context=ctx,
            intelligence_by_image=intel,
        )
        m1 = ReferenceManifest.model_validate(first.manifest)
        m2 = ReferenceManifest.model_validate(replay.manifest)
        assert m1.items[0].image_id == m2.items[0].image_id
        assert first.selector_trace["selector_policy_version"] == SELECTOR_POLICY_VERSION
        if first.selector_trace.get("weighted_rotation_enabled"):
            assert len(first.selector_trace.get("eligible_candidate_ids") or []) <= 3
        settings.grounded_rollout_mode = "studio"
        settings.quality_diversity_selector_mode = "off"
        grounded = resolve_generate_references(
            db,
            product_id=product_id,
            owner_user_id=owner_id,
            reference_count=1,
            use_scene_reference=False,
            source="studio",
        )
        assert grounded.selector_trace is None
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original
        settings.grounded_rollout_mode = grounded_original
        _cleanup(product_id)
