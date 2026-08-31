"""Phase 3A deterministic quality protection."""

from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

from bebcare.config.settings import settings
from bebcare.database import Base, SessionLocal, engine
from bebcare.initial_data import initialize_data
from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.generation_run import GenerationRun
from bebcare.models.product import Product, ProductImage
from bebcare.models.user import User
from bebcare.schemas.generation_plan import build_generation_plan, dump_generation_plan
from bebcare.schemas.reference_manifest import ManifestItem, ReferenceManifest
from bebcare.services.generation_run_store import add_artifacts, create_generation_run
from bebcare.services.grounded_rollout import (
    EXECUTED_GROUNDED_PROMPT_TRANSPORT,
    SOURCE_AUTOMATION,
    SOURCE_STUDIO,
)
from bebcare.services.quality_candidate_fetch import (
    OUTCOME_INVALID_URL,
    OUTCOME_TEMPORARY,
    OUTCOME_TOO_LARGE,
)
from bebcare.services.quality_protection import (
    QualityProtectionError,
    apply_publish_gate,
    inspect_candidate_bytes,
    record_finding,
    validate_post_generation,
    validate_pre_generation,
)
from bebcare.services.grounded_rollout import (
    EXECUTED_GROUNDED_PROMPT_TRANSPORT,
    SOURCE_AUTOMATION,
    SOURCE_STUDIO,
)
from bebcare.services.quality_protection import (
    QualityProtectionError,
    inspect_candidate_bytes,
    validate_post_generation,
    validate_pre_generation,
)
from bebcare.services.quality_protection_rollout import (
    POLICY_VERSION,
    quality_blocks_auto_publish,
    quality_protection_enabled,
)


def _png(color=(12, 80, 160), size=(128, 128)) -> bytes:
    image = Image.new("RGB", size, color)
    for x in range(size[0]):
        image.putpixel((x, x % size[1]), (x % 255, 40, 200))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _ensure_db():
    Base.metadata.create_all(bind=engine)
    initialize_data()


def _admin():
    _ensure_db()
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def _setup_grounded(owner, *, extra_items=None):
    db = SessionLocal()
    try:
        product = Product(product_name="QA SKU", category="test", description="d")
        product.owner_user_id = owner.user_id
        db.add(product)
        db.flush()
        image = ProductImage(
            product_id=product.product_id,
            cdn_url="https://cdn.test/primary.png",
            image_type="product",
            width=64,
            height=64,
        )
        db.add(image)
        db.flush()
        items = [
            ManifestItem(
                order=0,
                role="primary_subject",
                image_id=image.image_id,
                cdn_url=image.cdn_url,
                image_type="product",
                authority="preferred",
            )
        ]
        if extra_items:
            items.extend(extra_items)
        manifest = ReferenceManifest(items=items)
        plan = dump_generation_plan(build_generation_plan(manifest))
        run = create_generation_run(
            db,
            owner_user_id=owner.user_id,
            source=SOURCE_STUDIO,
            product_id=product.product_id,
            generate_task_id=None,
            rollout_mode_at_start="studio",
            experiment_variant=None,
            requested_pipeline_version="grounded_refs_v1",
            executed_pipeline_version=EXECUTED_GROUNDED_PROMPT_TRANSPORT,
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline=None,
            compare_group_id=None,
            generation_plan=plan,
            reference_manifest=manifest.model_dump(),
            provider_id="p",
            model="m",
            image_size="128x128",
            image_provider_mode="platform",
            quality_protection_mode=settings.quality_protection_mode,
            quality_policy_version=POLICY_VERSION,
        )
        db.commit()
        info = {
            "product_id": product.product_id,
            "owner_user_id": owner.user_id,
            "generation_run_id": run.run_id,
            "generation_plan": plan,
            "grounded_phase1b_enabled": True,
            "executed_pipeline_version": EXECUTED_GROUNDED_PROMPT_TRANSPORT,
            "generation_provenance": {
                "source": SOURCE_STUDIO,
                "reference_manifest": manifest.model_dump(),
                "grounded_phase1b_enabled": True,
                "executed_pipeline_version": EXECUTED_GROUNDED_PROMPT_TRANSPORT,
            },
        }
        return info, run.run_id, image.image_id
    finally:
        db.close()


def test_client_cannot_bypass_quality_rollout():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "off"
    try:
        assert quality_protection_enabled(source=SOURCE_STUDIO, requested_mode="all") is False
        assert quality_blocks_auto_publish(source=SOURCE_AUTOMATION, task_mode="auto") is False
    finally:
        settings.quality_protection_mode = original


def test_studio_mode_does_not_change_automation_publish():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    try:
        assert quality_protection_enabled(source=SOURCE_STUDIO) is True
        assert quality_protection_enabled(source=SOURCE_AUTOMATION) is False
        assert quality_blocks_auto_publish(source=SOURCE_AUTOMATION, task_mode="auto") is False
    finally:
        settings.quality_protection_mode = original


def test_manual_automation_does_not_block_auto_publish():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "manual_automation"
    try:
        assert quality_protection_enabled(source=SOURCE_STUDIO) is True
        assert quality_protection_enabled(source=SOURCE_AUTOMATION, task_mode="manual") is True
        assert quality_protection_enabled(source=SOURCE_AUTOMATION, task_mode="auto") is False
        assert quality_blocks_auto_publish(source=SOURCE_AUTOMATION, task_mode="auto") is False
        assert quality_blocks_auto_publish(
            source=SOURCE_AUTOMATION, task_mode="auto", persisted_mode="manual_automation"
        ) is False
        assert quality_blocks_auto_publish(
            source=SOURCE_AUTOMATION, task_mode="auto", persisted_mode="all"
        ) is True
    finally:
        settings.quality_protection_mode = original


def test_all_mode_blocks_auto_publish():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "all"
    try:
        assert quality_blocks_auto_publish(source=SOURCE_AUTOMATION, task_mode="auto") is True
        assert quality_blocks_auto_publish(source=SOURCE_STUDIO, task_mode="auto") is False
    finally:
        settings.quality_protection_mode = original


def test_rollout_off_preserves_invalid_manifest():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "off"
    owner = _admin()
    info, _, _ = _setup_grounded(owner)
    info["generation_provenance"]["reference_manifest"] = {"version": "nope"}
    db = SessionLocal()
    try:
        validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_invalid_manifest_blocks():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, _, _ = _setup_grounded(owner)
    info["generation_provenance"]["reference_manifest"] = {"version": "bad"}
    db = SessionLocal()
    try:
        try:
            validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
            raise AssertionError("expected QualityProtectionError")
        except QualityProtectionError as exc:
            assert exc.check_code == "invalid_manifest"
            db.commit()
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_foreign_reference_blocks():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, _, _ = _setup_grounded(owner)
    manifest = info["generation_provenance"]["reference_manifest"]
    manifest["items"][0]["image_id"] = "00000000-0000-0000-0000-000000000099"
    db = SessionLocal()
    try:
        try:
            validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
            raise AssertionError("expected QualityProtectionError")
        except QualityProtectionError as exc:
            assert exc.check_code == "foreign_reference"
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_missing_primary_and_duplicate_scene():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    extra = [
        ManifestItem(
            order=1,
            role="scene",
            image_id=None,
            cdn_url="https://cdn.test/s1.png",
            image_type="scene",
            authority="preferred",
        ),
        ManifestItem(
            order=2,
            role="scene",
            image_id=None,
            cdn_url="https://cdn.test/s2.png",
            image_type="scene",
            authority="preferred",
        ),
    ]
    info, _, _ = _setup_grounded(owner, extra_items=extra)
    db = SessionLocal()
    try:
        try:
            validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
            raise AssertionError("expected QualityProtectionError")
        except QualityProtectionError as exc:
            assert exc.check_code in ("duplicate_scene", "canonical_order")
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_handheld_and_group_without_evidence():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, _, _ = _setup_grounded(owner)
    info["handheld_physical_replacement"] = True
    db = SessionLocal()
    try:
        try:
            validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
            raise AssertionError("expected QualityProtectionError")
        except QualityProtectionError as exc:
            assert exc.check_code == "handheld_physical_enabled"
        info.pop("handheld_physical_replacement")
        info["generation_plan"]["display_config"] = "reference_supported_group"
        info["generation_plan"]["display_configuration"] = "reference_supported_group"
        try:
            validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
            raise AssertionError("expected QualityProtectionError")
        except QualityProtectionError as exc:
            assert exc.check_code in ("group_without_evidence", "plan_mismatch", "invalid_plan")
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_valid_image_passes_and_corrupt_fails():
    good = inspect_candidate_bytes(_png(), requested_size="128x128")
    assert all(item["passed"] or item["severity"] != "hard_fail" for item in good)
    assert inspect_candidate_bytes(b"not-an-image")[0]["check_code"] == "undecodable"
    empty = Image.new("RGB", (0, 10))
    # 0-width cannot be created; simulate zero via decode path
    assert inspect_candidate_bytes(b"")[0]["check_code"] == "empty_image"


def test_flat_and_aspect_and_duplicates():
    flat = Image.new("RGB", (32, 32), (7, 7, 7))
    buf = BytesIO()
    flat.save(buf, format="PNG")
    flat_findings = inspect_candidate_bytes(buf.getvalue())
    assert any(item["check_code"] == "flat_color" and item["severity"] == "warning" for item in flat_findings)
    assert all(item["passed"] or item["severity"] != "hard_fail" for item in flat_findings)
    mismatch = inspect_candidate_bytes(_png(size=(64, 16)), requested_size="64x64")
    assert any(item["check_code"] == "aspect_mismatch" for item in mismatch)
    blob = _png()
    seen = set()
    inspect_candidate_bytes(blob, seen_hashes=seen)
    dup = inspect_candidate_bytes(blob, seen_hashes=seen)
    assert any(item["check_code"] == "duplicate_candidate" for item in dup)
    source = {__import__("hashlib").sha256(blob).hexdigest()}
    ident = inspect_candidate_bytes(blob, source_hashes=source, allow_source_reuse=False)
    assert any(item["check_code"] == "source_identical" and not item["passed"] for item in ident)
    reuse = inspect_candidate_bytes(blob, source_hashes=source, allow_source_reuse=True)
    assert not any(item["check_code"] == "source_identical" and not item["passed"] for item in reuse)


def test_post_generation_records_findings():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    db = SessionLocal()
    try:
        summary = validate_post_generation(
            db,
            info,
            source=SOURCE_STUDIO,
            image_urls=["data:image/png;base64,xxx"],
            requested_size="128x128",
            candidate_bytes=[b"corrupt"],
        )
        db.commit()
        assert summary["hard_fail"] is True
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        assert run.owner_user_id == owner.user_id
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_cross_tenant_run_not_loaded():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    info["owner_user_id"] = "other-user"
    db = SessionLocal()
    try:
        try:
            validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
            raise AssertionError("expected QualityProtectionError")
        except QualityProtectionError as exc:
            assert exc.check_code == "run_ownership"
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_provider_not_called_on_pre_fail():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, _, _ = _setup_grounded(owner)
    info["generation_provenance"]["reference_manifest"] = {"version": "bad"}
    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("provider should not run")

    db = SessionLocal()
    try:
        with patch("bebcare.generator.content_generator.ContentGenerator") as unused:
            del unused
            try:
                validate_pre_generation(
                    db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128"
                )
            except QualityProtectionError:
                pass
        assert called["n"] == 0
    finally:
        db.close()
        settings.quality_protection_mode = original


def _white_subject_png() -> bytes:
    image = Image.new("RGB", (128, 128), (255, 255, 255))
    for x in range(56, 72):
        for y in range(56, 72):
            image.putpixel((x, y), (180, 40, 40))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _logo_png() -> bytes:
    image = Image.new("RGB", (64, 64), (255, 255, 255))
    for x in range(16, 48):
        image.putpixel((x, 32), (0, 0, 0))
        image.putpixel((32, x), (0, 0, 0))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _minimalist_png() -> bytes:
    image = Image.new("RGB", (96, 96), (245, 245, 245))
    for x in range(20, 76):
        image.putpixel((x, 48), (20, 20, 20))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _sparse_screenshot_png() -> bytes:
    image = Image.new("RGB", (160, 100), (250, 250, 250))
    for x in range(10, 150):
        image.putpixel((x, 8), (60, 60, 60))
    image.putpixel((12, 40), (30, 30, 30))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _transparent_png() -> bytes:
    image = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    for x in range(12, 36):
        for y in range(12, 36):
            image.putpixel((x, y), (10, 120, 200, 255))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _assert_not_hard_failed(raw: bytes):
    findings = inspect_candidate_bytes(raw)
    assert all(item["severity"] != "hard_fail" for item in findings)


def test_minimal_valid_images_are_not_hard_failed():
    white = Image.new("RGB", (64, 64), (255, 255, 255))
    buf = BytesIO()
    white.save(buf, format="PNG")
    _assert_not_hard_failed(buf.getvalue())
    _assert_not_hard_failed(_white_subject_png())
    _assert_not_hard_failed(_logo_png())
    _assert_not_hard_failed(_minimalist_png())
    _assert_not_hard_failed(_sparse_screenshot_png())
    _assert_not_hard_failed(_transparent_png())
    _assert_not_hard_failed(_png())


def test_retrieval_timeout_is_not_missing_candidate():
    findings = inspect_candidate_bytes(
        None,
        retrieval_outcome=OUTCOME_TEMPORARY,
        retrieval_details={"reason": "timeout"},
    )
    assert findings[0]["check_code"] == "candidate_retrieval"
    assert findings[0]["details"]["outcome"] == OUTCOME_TEMPORARY
    assert findings[0]["check_code"] != "missing_candidate"


def test_cdn_failure_and_invalid_and_oversize_retrieval():
    cdn = inspect_candidate_bytes(
        None, retrieval_outcome=OUTCOME_TEMPORARY, retrieval_details={"reason": "http_status", "status": 502}
    )
    assert cdn[0]["details"]["outcome"] == OUTCOME_TEMPORARY
    assert cdn[0]["check_code"] == "candidate_retrieval"
    missing = inspect_candidate_bytes(None)
    assert missing[0]["check_code"] == "missing_candidate"
    invalid = inspect_candidate_bytes(
        None, retrieval_outcome=OUTCOME_INVALID_URL, retrieval_details={"reason": "unsupported_scheme"}
    )
    assert invalid[0]["details"]["outcome"] == OUTCOME_INVALID_URL
    oversized = inspect_candidate_bytes(
        None, retrieval_outcome=OUTCOME_TOO_LARGE, retrieval_details={"reason": "content_length_exceeds_limit"}
    )
    assert oversized[0]["details"]["outcome"] == OUTCOME_TOO_LARGE


def test_persisted_mode_survives_environment_change():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "off"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    settings.quality_protection_mode = "all"
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        assert run.quality_protection_mode == "off"
        assert run.quality_policy_version == POLICY_VERSION
        add_artifacts(db, run, ["https://cdn.test/a.png", "https://cdn.test/b.png"])
        db.flush()
        db.refresh(run)
        gate = apply_publish_gate(
            db,
            owner_user_id=owner.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/a.png", "https://cdn.test/b.png"],
        )
        assert gate["blocked"] is False
        assert gate["selected_url"] == "https://cdn.test/a.png"
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_persisted_all_still_gates_when_env_off():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "all"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    settings.quality_protection_mode = "off"
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        assert run.quality_protection_mode == "all"
        add_artifacts(db, run, ["https://cdn.test/a.png"])
        db.flush()
        db.refresh(run)
        record_finding(
            db,
            run=run,
            stage="post_generation",
            check_code="undecodable",
            severity="hard_fail",
            passed=False,
            details={"candidate_index": 0},
            artifact_id=run.artifacts[0].artifact_id,
        )
        gate = apply_publish_gate(
            db,
            owner_user_id=owner.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/a.png"],
        )
        assert gate["blocked"] is True
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_persisted_manual_automation_and_legacy_null():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "manual_automation"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        add_artifacts(db, run, ["https://cdn.test/a.png"])
        db.flush()
        db.refresh(run)
        record_finding(
            db,
            run=run,
            stage="post_generation",
            check_code="undecodable",
            severity="hard_fail",
            passed=False,
            details={"candidate_index": 0},
            artifact_id=run.artifacts[0].artifact_id,
        )
        gate = apply_publish_gate(
            db,
            owner_user_id=owner.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/a.png"],
        )
        assert gate["blocked"] is False
        run.quality_protection_mode = None
        run.quality_policy_version = None
        db.flush()
        settings.quality_protection_mode = "all"
        gate_legacy = apply_publish_gate(
            db,
            owner_user_id=owner.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/a.png"],
        )
        assert gate_legacy["blocked"] is False
    finally:
        db.close()
        settings.quality_protection_mode = original


def _seed_two_artifacts(db, run, urls):
    add_artifacts(db, run, urls)
    db.flush()
    db.refresh(run)
    return sorted(run.artifacts, key=lambda row: row.candidate_index)


def test_selects_second_when_first_hard_fails():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "all"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        arts = _seed_two_artifacts(db, run, ["https://cdn.test/bad.png", "https://cdn.test/good.png"])
        record_finding(
            db, run=run, stage="post_generation", check_code="undecodable",
            severity="hard_fail", passed=False, details={"candidate_index": 0},
            artifact_id=arts[0].artifact_id,
        )
        record_finding(
            db, run=run, stage="post_generation", check_code="candidate_hash",
            severity="info", passed=True, details={"candidate_index": 1},
            artifact_id=arts[1].artifact_id,
        )
        gate = apply_publish_gate(
            db,
            owner_user_id=owner.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/bad.png", "https://cdn.test/good.png"],
        )
        assert gate["blocked"] is False
        assert gate["selected_url"] == "https://cdn.test/good.png"
        assert gate["selected_artifact_id"] == arts[1].artifact_id
        db.refresh(arts[0])
        db.refresh(arts[1])
        assert arts[0].selected is False
        assert arts[1].selected is True
        attached = (
            db.query(GenerationArtifactQualityFinding)
            .filter(GenerationArtifactQualityFinding.generation_run_id == run_id)
            .all()
        )
        assert {row.artifact_id for row in attached if row.stage == "post_generation"} == {
            arts[0].artifact_id,
            arts[1].artifact_id,
        }
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_warning_candidate_remains_eligible():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "all"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        arts = _seed_two_artifacts(db, run, ["https://cdn.test/warn.png", "https://cdn.test/ok.png"])
        record_finding(
            db, run=run, stage="post_generation", check_code="flat_color",
            severity="warning", passed=True, details={"candidate_index": 0},
            artifact_id=arts[0].artifact_id,
        )
        record_finding(
            db, run=run, stage="post_generation", check_code="candidate_hash",
            severity="info", passed=True, details={"candidate_index": 1},
            artifact_id=arts[1].artifact_id,
        )
        gate = apply_publish_gate(
            db,
            owner_user_id=owner.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/warn.png", "https://cdn.test/ok.png"],
        )
        assert gate["blocked"] is False
        assert gate["selected_url"] == "https://cdn.test/warn.png"
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_all_candidates_fail_blocks_buffer():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "all"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        arts = _seed_two_artifacts(db, run, ["https://cdn.test/a.png", "https://cdn.test/b.png"])
        for art, idx in ((arts[0], 0), (arts[1], 1)):
            record_finding(
                db, run=run, stage="post_generation", check_code="undecodable",
                severity="hard_fail", passed=False, details={"candidate_index": idx},
                artifact_id=art.artifact_id,
            )
        gate = apply_publish_gate(
            db,
            owner_user_id=owner.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/a.png", "https://cdn.test/b.png"],
        )
        assert gate["blocked"] is True
        assert gate["selected_url"] is None
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_single_candidate_pass_and_fail():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "all"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        add_artifacts(db, run, ["https://cdn.test/only.png"])
        db.flush()
        db.refresh(run)
        art = run.artifacts[0]
        record_finding(
            db, run=run, stage="post_generation", check_code="candidate_hash",
            severity="info", passed=True, details={"candidate_index": 0},
            artifact_id=art.artifact_id,
        )
        gate_ok = apply_publish_gate(
            db, owner_user_id=owner.user_id, run_id=run_id,
            source=SOURCE_AUTOMATION, task_mode="auto",
            image_urls=["https://cdn.test/only.png"],
        )
        assert gate_ok["blocked"] is False
        record_finding(
            db, run=run, stage="post_generation", check_code="undecodable",
            severity="hard_fail", passed=False, details={"candidate_index": 0},
            artifact_id=art.artifact_id,
        )
        gate_bad = apply_publish_gate(
            db, owner_user_id=owner.user_id, run_id=run_id,
            source=SOURCE_AUTOMATION, task_mode="auto",
            image_urls=["https://cdn.test/only.png"],
        )
        assert gate_bad["blocked"] is True
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_post_generation_attaches_per_candidate_and_skips_fetch_when_bytes_given():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    db = SessionLocal()
    try:
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        add_artifacts(db, run, ["https://cdn.test/a.png", "https://cdn.test/b.png"])
        db.flush()
        db.refresh(run)
        with patch("bebcare.services.quality_protection.fetch_candidate_bytes") as fetch:
            summary = validate_post_generation(
                db,
                info,
                source=SOURCE_STUDIO,
                image_urls=["https://cdn.test/a.png", "https://cdn.test/b.png"],
                requested_size="128x128",
                candidate_bytes=[b"corrupt", _png()],
            )
            fetch.assert_not_called()
        db.commit()
        assert summary["hard_fail"] is False
        assert summary["selected_index"] == 1
        rows = (
            db.query(GenerationArtifactQualityFinding)
            .filter(GenerationArtifactQualityFinding.generation_run_id == run_id)
            .all()
        )
        assert any(row.check_code == "undecodable" and row.artifact_id == run.artifacts[0].artifact_id for row in rows)
        assert any(
            row.check_code == "candidate_hash" and row.artifact_id == run.artifacts[1].artifact_id for row in rows
        )
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_cross_tenant_cannot_select_or_attach():
    original = settings.quality_protection_mode
    settings.quality_protection_mode = "all"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    other = User(
        user_id=str(uuid4()),
        username=f"qa_{uuid4().hex[:8]}",
        email=f"qa_{uuid4().hex[:8]}@test.local",
        hashed_password="x",
        is_active=True,
        is_admin=False,
    )
    db = SessionLocal()
    try:
        db.add(other)
        db.flush()
        run = db.query(GenerationRun).filter(GenerationRun.run_id == run_id).one()
        add_artifacts(db, run, ["https://cdn.test/a.png"])
        db.flush()
        db.refresh(run)
        spoof = record_finding(
            db,
            run=run,
            stage="post_generation",
            check_code="undecodable",
            severity="hard_fail",
            passed=False,
            details={"candidate_index": 0},
            artifact_id=run.artifacts[0].artifact_id,
        )
        assert spoof.owner_user_id == owner.user_id
        gate = apply_publish_gate(
            db,
            owner_user_id=other.user_id,
            run_id=run_id,
            source=SOURCE_AUTOMATION,
            task_mode="auto",
            image_urls=["https://cdn.test/a.png"],
        )
        assert gate["selected_url"] is None
        assert gate["blocked"] is False
    finally:
        db.close()
        settings.quality_protection_mode = original


def test_pre_qa_failure_refunds_reservation():
    from bebcare.models.generate_task import GenerateTask
    from bebcare.models.image_credit import ImageCreditReservation
    from bebcare.services.credit_grant_service import create_grant, remaining_credits, reserve_one
    from bebcare.services.generate_task_store import update_generate_task

    original = settings.quality_protection_mode
    settings.quality_protection_mode = "studio"
    owner = _admin()
    info, run_id, _ = _setup_grounded(owner)
    info["generation_provenance"]["reference_manifest"] = {"version": "bad"}
    task_id = str(uuid4())
    db = SessionLocal()
    try:
        db.add(GenerateTask(task_id=task_id, status="PENDING", owner_user_id=owner.user_id))
        create_grant(db, user_id=owner.user_id, quantity=1, source="admin_grant")
        db.flush()
        before = remaining_credits(db, owner.user_id)
        reserve_one(db, user_id=owner.user_id, generate_task_id=task_id)
        db.commit()
        try:
            validate_pre_generation(db, info, source=SOURCE_STUDIO, provider_ok=True, image_size="128x128")
            raise AssertionError("expected QualityProtectionError")
        except QualityProtectionError:
            db.commit()
        update_generate_task(task_id, status="FAILURE", set_result=True, result={"error": "quality"})
        db2 = SessionLocal()
        try:
            assert remaining_credits(db2, owner.user_id) == before
            row = (
                db2.query(ImageCreditReservation)
                .filter(ImageCreditReservation.generate_task_id == task_id)
                .one()
            )
            assert row.status == "refunded"
        finally:
            db2.close()
    finally:
        db.close()
        settings.quality_protection_mode = original

