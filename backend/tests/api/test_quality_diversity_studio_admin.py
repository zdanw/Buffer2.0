"""Studio reference-selection and admin QDS history. No paid provider calls."""

from datetime import datetime
from uuid import uuid4

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.product import Product, ProductImage
from bebcare.models.product_image_analysis import ProductImageAnalysis
from bebcare.models.user import User
from bebcare.schemas.asset_intelligence import SEMANTIC_SCHEMA_VERSION, offering_context_for_product
from bebcare.services.asset_intelligence_adapter import analysis_model_version
from bebcare.services.generation_plan import attach_generation_plan
from bebcare.services.generation_run_store import create_generation_run
from bebcare.services.grounded_rollout import SOURCE_STUDIO, selection_provenance
from bebcare.services.ownership import stamp_owner
from bebcare.services.quality_diversity_events import attach_from_product_info
from bebcare.utils.grounded_reference_selector import select_grounded_references
from tests.unit.qds_semantic_fixtures import (
    geometry_high,
    geometry_low,
    geometry_mid,
    lifestyle_excluded,
    packaging_excluded,
)


def _admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def _seed_product(owner):
    db = SessionLocal()
    try:
        product = Product(
            product_name="QDS studio API",
            category="test",
            description="studio qds",
            offering_type="physical_product",
        )
        stamp_owner(product, owner)
        db.add(product)
        db.flush()
        ctx = offering_context_for_product(product)
        model_v = analysis_model_version()
        intels = [geometry_high(), geometry_mid(), geometry_low(), lifestyle_excluded(), packaging_excluded()]
        widths = [2000, 700, 380, 1800, 1400]
        phashes = ["1111111111111111", "2222222222222222", "3333333333333333", "4444444444444444", "5555555555555555"]
        ids = []
        for index, intel in enumerate(intels):
            row = ProductImage(
                product_id=product.product_id,
                cdn_url=f"https://cdn.test/api-{index}.jpg",
                phash=phashes[index],
                width=widths[index],
                height=2000 if index < 3 else 1400,
                image_type="product",
                sort_index=index,
                uploaded_at=datetime.utcnow(),
                content_hash=uuid4().hex,
                analysis_status="ready",
            )
            db.add(row)
            db.flush()
            ids.append(row.image_id)
            analysis = ProductImageAnalysis(
                product_image_id=row.image_id,
                content_hash=row.content_hash,
                schema_version=SEMANTIC_SCHEMA_VERSION,
                model_version=model_v,
                offering_context_version=ctx,
                status="ready",
                normalized_result=intel.model_dump(),
                analyzed_at=datetime.utcnow(),
            )
            stamp_owner(analysis, owner)
            db.add(analysis)
        db.commit()
        return str(product.product_id), ids, str(owner.user_id)
    finally:
        db.close()


def test_studio_reference_selection_and_admin_history(full_client, auth_headers):
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "studio"
    owner = _admin()
    product_id, ids, owner_id = _seed_product(owner)
    try:
        listed = full_client.get("/v1/admin/generation-runs", headers=auth_headers)
        assert listed.status_code == 200
        denied = full_client.get("/v1/admin/generation-runs")
        assert denied.status_code in (401, 403)

        live = full_client.post(
            "/v1/generate/reference-selection/",
            headers=auth_headers,
            json={"product_id": product_id, "reference_count": 2, "use_scene_reference": False, "image_size": "1:1"},
        )
        assert live.status_code == 200, live.text
        body = live.json()
        assert body["reference_product_image_ids"]
        assert ids[3] not in body["reference_product_image_ids"]
        assert ids[4] not in body["reference_product_image_ids"]

        db = SessionLocal()
        try:
            selected = select_grounded_references(
                db,
                product_id,
                2,
                False,
                owner_user_id=owner_id,
                image_size="1:1",
                source=SOURCE_STUDIO,
                selection_seed="studio-api-74",
            )
            info = {
                "product_id": product_id,
                "owner_user_id": owner_id,
                "grounded_phase1b_enabled": True,
                "generation_provenance": selection_provenance(selected, source=SOURCE_STUDIO),
                "reference_manifest": selected.manifest,
            }
            attach_generation_plan(info)
            run = create_generation_run(
                db,
                owner_user_id=owner_id,
                source=SOURCE_STUDIO,
                product_id=product_id,
                generate_task_id=None,
                rollout_mode_at_start="studio",
                experiment_variant=selected.experiment_variant,
                requested_pipeline_version=selected.requested_pipeline_version,
                executed_pipeline_version=selected.executed_pipeline_version,
                fallback_reason=selected.fallback_reason,
                fallback_path=selected.fallback_path,
                image_prompt_pipeline=None,
                compare_group_id=None,
                generation_plan=info.get("generation_plan"),
                reference_manifest=selected.manifest,
                provider_id=None,
                model=None,
                image_size="1:1",
                image_provider_mode="platform",
                requested_selector_strategy=selected.requested_selector_strategy,
                executed_selector_strategy=selected.executed_selector_strategy,
                selection_seed=selected.selection_seed,
            )
            attach_from_product_info(db, run, info, source=SOURCE_STUDIO)
            run.status = "succeeded"
            db.commit()
            run_id = run.run_id
        finally:
            db.close()

        leak_user = full_client.post(
            "/v1/auth/users",
            headers=auth_headers,
            json={
                "username": f"qdsleak{uuid4().hex[:6]}",
                "email": f"leak{uuid4().hex[:6]}@test.local",
                "password": "UserTestPass123!",
                "is_admin": False,
            },
        )
        assert leak_user.status_code == 201
        db = SessionLocal()
        try:
            from bebcare.models.generation_qds import GenerationDecisionEvent

            db.add(
                GenerationDecisionEvent(
                    generation_run_id=run_id,
                    sequence_number=999,
                    event_type="foreign_owner_leak",
                    stage="select",
                    severity="info",
                    summary="LEAK",
                    owner_user_id=leak_user.json()["user_id"],
                )
            )
            db.commit()
        finally:
            db.close()

        compact = full_client.get(f"/v1/admin/generation-runs/{run_id}/history", headers=auth_headers)
        expanded = full_client.get(
            f"/v1/admin/generation-runs/{run_id}/history",
            headers=auth_headers,
            params={"expanded": "true"},
        )
        assert compact.status_code == 200
        assert expanded.status_code == 200
        compact_body = compact.json()
        assert compact_body["run_id"] == run_id
        assert compact_body["seed"] == "studio-api-74"
        types = {e["event_type"] for e in compact_body.get("events") or []}
        assert "qds_enabled" in types
        assert "foreign_owner_leak" not in types
        assert all(e.get("summary") != "LEAK" for e in compact_body.get("events") or [])
        assert compact_body.get("coverage")
        detail = full_client.get(f"/v1/admin/generation-runs/{run_id}", headers=auth_headers)
        assert detail.status_code == 200
        diag = detail.json().get("generation_diagnostics") or {}
        assert diag.get("run_id") == run_id
        assert diag.get("has_history") is True
        keys = {row["key"] for row in diag.get("summary") or []}
        assert "diversity" in keys
        assert diag.get("technical")
        blob = str(diag)
        assert "api_key" not in blob.lower()
        assert "sk-" not in blob
        assert expanded.json().get("expanded") is True
        assert all(
            e.get("event_type") != "foreign_owner_leak"
            for e in expanded.json().get("event_details") or []
        )

        user = full_client.post(
            "/v1/auth/users",
            headers=auth_headers,
            json={
                "username": f"qdsuser{uuid4().hex[:6]}",
                "email": f"qds{uuid4().hex[:6]}@test.local",
                "password": "UserTestPass123!",
                "is_admin": False,
            },
        )
        assert user.status_code == 201
        login = full_client.post(
            "/v1/auth/login/",
            data={"username": user.json()["username"], "password": "UserTestPass123!"},
        )
        other = {"Authorization": f"Bearer {login.json()['access_token']}"}
        blocked = full_client.get(f"/v1/admin/generation-runs/{run_id}/history", headers=other)
        assert blocked.status_code in (401, 403)
    finally:
        settings.quality_diversity_selector_mode = original
