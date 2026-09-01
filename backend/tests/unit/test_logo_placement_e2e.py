"""Local E2E: persist pre-composite QA flags and publication gating for logo placement."""

from uuid import uuid4

from bebcare.config.settings import settings
from bebcare.database import Base, SessionLocal, engine
from bebcare.initial_data import initialize_data
from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.user import User
from bebcare.schemas.visual_fidelity import VisualFidelityAssessment, VisualFidelityCheck, publication_decision_from_checks
from bebcare.services.generation_run_store import add_artifacts, create_generation_run
from bebcare.services.grounded_rollout import SOURCE_AUTOMATION, SOURCE_STUDIO
from bebcare.services.quality_protection import apply_publish_gate
from bebcare.services.visual_fidelity_qa import persist_assessment


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


def _assessment(checks, **kwargs):
    return VisualFidelityAssessment(
        candidate_index=kwargs.get("candidate_index", 0),
        checks=checks,
        overall_publication_decision=publication_decision_from_checks(checks),
        model_version="test-vision",
    )


def test_pre_composite_persist_and_studio_does_not_block():
    _ensure_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first()
        run = _run(db, owner_id=user.user_id, source=SOURCE_STUDIO, visual_fidelity_qa_mode="studio")
        add_artifacts(db, run, ["https://cdn.example.test/cam.jpg"])
        persist_assessment(
            db,
            run,
            _assessment(
                [
                    VisualFidelityCheck(
                        check_code="logo_on_unsupported_surface",
                        status="hard_fail",
                        confidence="high",
                    )
                ]
            ),
            cache_key=f"logo-e2e-{uuid4().hex}",
            composite_logo=True,
            pre_composite=True,
        )
        db.commit()
        row = (
            db.query(GenerationArtifactQualityFinding)
            .filter(GenerationArtifactQualityFinding.generation_run_id == run.run_id)
            .first()
        )
        details = row.details or {}
        assert details.get("pre_composite") is True
        assert details.get("composited_output_checked") is False
        assert details.get("publication_note") is None
        gate = apply_publish_gate(
            db,
            owner_user_id=user.user_id,
            run_id=run.run_id,
            source=SOURCE_STUDIO,
            task_mode="manual",
            image_urls=["https://cdn.example.test/cam.jpg"],
        )
        assert gate["blocked"] is False
    finally:
        db.close()


def test_auto_publish_blocks_when_all_logo_hard_fails():
    _ensure_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first()
        run = _run(
            db,
            owner_id=user.user_id,
            source=SOURCE_AUTOMATION,
            visual_fidelity_qa_mode="auto_publish",
        )
        add_artifacts(db, run, ["https://cdn.example.test/a.jpg"])
        persist_assessment(
            db,
            run,
            _assessment(
                [
                    VisualFidelityCheck(
                        check_code="invented_logo",
                        status="hard_fail",
                        confidence="high",
                    )
                ]
            ),
            cache_key=f"logo-e2e-block-{uuid4().hex}",
            composite_logo=True,
            pre_composite=True,
        )
        db.commit()
        original = settings.visual_fidelity_qa_mode
        settings.visual_fidelity_qa_mode = "auto_publish"
        try:
            gate = apply_publish_gate(
                db,
                owner_user_id=user.user_id,
                run_id=run.run_id,
                source=SOURCE_AUTOMATION,
                task_mode="auto",
                image_urls=["https://cdn.example.test/a.jpg"],
            )
            assert gate["blocked"] is True
        finally:
            settings.visual_fidelity_qa_mode = original
    finally:
        db.close()
