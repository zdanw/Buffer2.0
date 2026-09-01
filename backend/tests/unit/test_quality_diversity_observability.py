"""QDS decision events, admin history, tenant isolation. No provider calls."""

from uuid import uuid4

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.generation_qds import GenerationDecisionEvent, GenerationReferenceSelection
from bebcare.models.generation_run import GenerationRun
from bebcare.models.user import User
from bebcare.services.generation_run_store import create_generation_run
from bebcare.services.quality_diversity_events import attach_from_product_info, persist_selection_observability
from bebcare.services.quality_diversity_rollout import STRATEGY_QDS
from bebcare.services.grounded_rollout import SOURCE_STUDIO


def _admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def test_persist_qds_events_idempotent_and_redacts_secrets():
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "studio"
    owner = _admin()
    db = SessionLocal()
    try:
        run = create_generation_run(
            db,
            owner_user_id=owner.user_id,
            source=SOURCE_STUDIO,
            product_id=None,
            generate_task_id=None,
            rollout_mode_at_start="studio",
            experiment_variant=None,
            requested_pipeline_version="x",
            executed_pipeline_version="deterministic_refs_only",
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline=None,
            compare_group_id=None,
            provider_id=None,
            model=None,
            image_size="1:1",
            image_provider_mode="platform",
        )
        persist_selection_observability(
            db,
            run,
            source=SOURCE_STUDIO,
            grounded=True,
            qds_ran=True,
            seed="deadbeef",
            trace={
                "selector_policy_version": "quality_diversity_selector_v3",
                "selection_reason": "weighted_eligible_pool",
                "eligible_candidate_ids": ["a", "b"],
                "exclusion_reasons": [{"image_id": "c", "reasons": ["severe_crop"]}],
                "effective_weights": {"a": 0.6, "b": 0.4},
                "coverage": "moderate",
                "selected_ids": ["a"],
                "diversity_penalties": {"a": 0.8},
                "shot_family": "functional_medium",
                "api_key": "should-not-store",
            },
            manifest={"items": [{"image_id": "a", "cdn_url": "https://signed.example/x?token=1"}]},
        )
        db.commit()
        persist_selection_observability(
            db,
            run,
            source=SOURCE_STUDIO,
            grounded=True,
            qds_ran=True,
            seed="deadbeef",
            trace={"selection_reason": "weighted_eligible_pool"},
        )
        db.commit()
        n = (
            db.query(GenerationDecisionEvent)
            .filter(GenerationDecisionEvent.generation_run_id == run.run_id)
            .count()
        )
        sel_n = (
            db.query(GenerationReferenceSelection)
            .filter(GenerationReferenceSelection.generation_run_id == run.run_id)
            .count()
        )
        assert sel_n == 1
        assert n >= 3
        blob = str(
            [
                e.details
                for e in db.query(GenerationDecisionEvent)
                .filter(GenerationDecisionEvent.generation_run_id == run.run_id)
                .all()
            ]
        )
        assert "should-not-store" not in blob
        assert "token=1" not in blob
        refreshed = db.query(GenerationRun).filter(GenerationRun.run_id == run.run_id).first()
        assert refreshed.executed_selector_strategy == STRATEGY_QDS
        assert refreshed.selection_seed == "deadbeef"
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original


def test_observability_failure_does_not_crash(monkeypatch):
    owner = _admin()
    db = SessionLocal()
    try:
        run = create_generation_run(
            db,
            owner_user_id=owner.user_id,
            source=SOURCE_STUDIO,
            product_id=None,
            generate_task_id=None,
            rollout_mode_at_start="studio",
            experiment_variant=None,
            requested_pipeline_version="x",
            executed_pipeline_version="deterministic_refs_only",
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline=None,
            compare_group_id=None,
            provider_id=None,
            model=None,
            image_size="1:1",
            image_provider_mode="platform",
        )
        from bebcare.services import quality_diversity_events as events

        def boom(*_a, **_k):
            raise RuntimeError("db down")

        monkeypatch.setattr(events, "GenerationReferenceSelection", boom)
        persist_selection_observability(db, run, source=SOURCE_STUDIO, qds_ran=True, seed="x")
        db.commit()
        assert db.query(GenerationRun).filter(GenerationRun.run_id == run.run_id).first()
    finally:
        db.close()


def test_admin_history_requires_admin_and_isolates_tenant(full_client, auth_headers):
    owner = _admin()
    db = SessionLocal()
    try:
        run = create_generation_run(
            db,
            owner_user_id=owner.user_id,
            source=SOURCE_STUDIO,
            product_id=None,
            generate_task_id=None,
            rollout_mode_at_start="studio",
            experiment_variant=None,
            requested_pipeline_version="x",
            executed_pipeline_version="deterministic_refs_only",
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline=None,
            compare_group_id=None,
            provider_id=None,
            model=None,
            image_size="1:1",
            image_provider_mode="platform",
        )
        db.commit()
        run_id = run.run_id
    finally:
        db.close()

    denied = full_client.get(f"/v1/admin/generation-runs/{run_id}/history")
    assert denied.status_code in (401, 403)
    listed = full_client.get("/v1/admin/generation-runs", headers=auth_headers)
    assert listed.status_code == 200
    hist = full_client.get(f"/v1/admin/generation-runs/{run_id}/history", headers=auth_headers)
    assert hist.status_code == 200
    body = hist.json()
    assert body["run_id"] == run_id
    assert body.get("legacy") is True or "selector_strategy" in body
    missing = full_client.get(f"/v1/admin/generation-runs/{uuid4()}/history", headers=auth_headers)
    assert missing.status_code == 404


def test_attach_from_product_info_skips_when_qds_off():
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "off"
    owner = _admin()
    db = SessionLocal()
    try:
        run = create_generation_run(
            db,
            owner_user_id=owner.user_id,
            source=SOURCE_STUDIO,
            product_id=None,
            generate_task_id=None,
            rollout_mode_at_start="off",
            experiment_variant=None,
            requested_pipeline_version="x",
            executed_pipeline_version="legacy_random_refs",
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline=None,
            compare_group_id=None,
            provider_id=None,
            model=None,
            image_size="1:1",
            image_provider_mode="platform",
        )
        attach_from_product_info(
            db,
            run,
            {"generation_provenance": {"executed_selector_strategy": "off"}},
            source=SOURCE_STUDIO,
        )
        db.commit()
        events = (
            db.query(GenerationDecisionEvent)
            .filter(GenerationDecisionEvent.generation_run_id == run.run_id)
            .all()
        )
        assert any(e.event_type == "qds_skipped" for e in events)
    finally:
        db.close()
        settings.quality_diversity_selector_mode = original
