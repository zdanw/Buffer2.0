"""Phase 2B retry classification, JSON correction, and unique-cache races."""

from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch

import httpx
from PIL import Image

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.product import Product, ProductImage
from bebcare.models.product_image_analysis import ProductImageAnalysis
from bebcare.models.user import User
from bebcare.schemas.asset_intelligence import (
    SEMANTIC_SCHEMA_VERSION,
    offering_context_for_product,
    offering_context_version,
)
from bebcare.services.asset_intelligence import (
    _analyze_one,
    analysis_for_image,
    enqueue_selected_intelligence,
    run_intelligence_job,
)
from bebcare.services.asset_intelligence_adapter import (
    aggregate_usage,
    analysis_model_version,
    analyze_reference_image,
    assert_analysis_image_url,
)
from bebcare.services.asset_intelligence_policy import (
    FAILURE_PERMANENT,
    FAILURE_TRANSIENT,
    MAX_ANALYSIS_ATTEMPTS,
    AnalysisFailure,
    classify_analysis_failure,
    is_retry_eligible,
    is_usable_cache_hit,
    next_retry_at_for_attempt,
)
from bebcare.services.deterministic_metadata import content_hash_bytes
from bebcare.utils.reference_selector import resolve_generate_references


def _png(color=(1, 2, 3, 255), size=(48, 48)) -> bytes:
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


def _product(owner, name="Retry SKU"):
    db = SessionLocal()
    try:
        product = Product(
            product_name=name, category="test", description="d", offering_type="unknown"
        )
        product.owner_user_id = owner.user_id
        db.add(product)
        db.commit()
        return product.product_id
    finally:
        db.close()


def _image(db, product_id, raw):
    digest = content_hash_bytes(raw)
    row = ProductImage(
        product_id=product_id,
        cdn_url=f"https://cdn.test/{digest[:10]}.png",
        image_type="product",
        width=48,
        height=48,
        content_hash=digest,
        analysis_status="ready",
        deterministic_metadata_version="det_meta_v1",
    )
    db.add(row)
    db.flush()
    return row


def _ok_body():
    return {
        "asset_source_type": "product",
        "subject_or_scene": "subject",
        "people_or_hands_presence": "absent",
        "text_presence": "absent",
        "brand_mark_presence": "unknown",
        "broad_composition": "centered",
        "broad_lighting": "studio",
        "screenshot_or_interface_presence": "absent",
        "packaging_presence": "absent",
        "dominant_offering_evidence": "unknown",
        "generation_suitability": "primary_subject",
        "confidence": "low",
        "warnings": [],
    }


def _http_status(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("http", request=request, response=response)


def test_timeout_classified_transient():
    kind, cat = classify_analysis_failure(httpx.TimeoutException("t"))
    assert kind == FAILURE_TRANSIENT
    assert cat == "timeout"


def test_connection_error_classified_transient():
    kind, cat = classify_analysis_failure(httpx.ConnectError("c"))
    assert kind == FAILURE_TRANSIENT
    assert cat == "connection_error"


def test_http_429_classified_transient():
    kind, cat = classify_analysis_failure(_http_status(429))
    assert kind == FAILURE_TRANSIENT
    assert cat == "http_429"


def test_http_408_classified_transient():
    kind, cat = classify_analysis_failure(_http_status(408))
    assert kind == FAILURE_TRANSIENT
    assert cat == "http_408"


def test_http_500_classified_transient():
    kind, cat = classify_analysis_failure(_http_status(500))
    assert kind == FAILURE_TRANSIENT
    assert cat == "http_5xx"


def test_http_400_classified_permanent():
    kind, cat = classify_analysis_failure(_http_status(400))
    assert kind == FAILURE_PERMANENT
    assert cat == "http_400_invalid_request"


def test_http_401_403_classified_permanent():
    assert classify_analysis_failure(_http_status(401)) == (FAILURE_PERMANENT, "http_auth")
    assert classify_analysis_failure(_http_status(403)) == (FAILURE_PERMANENT, "http_auth")


def test_adapter_maps_http_400_and_401_to_analysis_failure():
    def bad_request(messages):
        raise _http_status(400)

    try:
        analyze_reference_image(
            image_url="https://cdn.test/a.png", offering_type="unknown", complete=bad_request
        )
        raise AssertionError("expected AnalysisFailure")
    except AnalysisFailure as exc:
        assert exc.failure_type == FAILURE_PERMANENT
        assert exc.error_category == "http_400_invalid_request"

    def unauthorized(messages):
        raise _http_status(401)

    try:
        analyze_reference_image(
            image_url="https://cdn.test/a.png", offering_type="unknown", complete=unauthorized
        )
        raise AssertionError("expected AnalysisFailure")
    except AnalysisFailure as exc:
        assert exc.failure_type == FAILURE_PERMANENT
        assert exc.error_category == "http_auth"


def test_backoff_schedule():
    now = datetime(2026, 8, 31, 0, 0, 0)
    first = next_retry_at_for_attempt(1, now=now)
    second = next_retry_at_for_attempt(2, now=now)
    third = next_retry_at_for_attempt(3, now=now)
    assert first == now + timedelta(minutes=5)
    assert second == now + timedelta(minutes=30)
    assert third is None


def _run_failing_job(complete, *, color=(9, 8, 7, 255), name="Fail Job"):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, name)
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png(color))
        db.commit()
        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=complete,
        )
        row = analysis_for_image(
            db,
            owner_user_id=owner.user_id,
            image=image,
            offering_type="unknown",
            product=db.query(Product).filter(Product.product_id == product_id).one(),
        )
        return db, owner, product_id, image, row
    except Exception:
        db.close()
        settings.asset_intelligence_mode = original
        raise


def test_transient_timeout_retryable_after_backoff(client):
    original = settings.asset_intelligence_mode
    db = None
    try:

        def boom(messages):
            raise httpx.TimeoutException("timeout")

        db, owner, product_id, image, row = _run_failing_job(
            boom, color=(12, 13, 14, 255), name="Timeout Row"
        )
        assert row.status == "failed"
        assert row.failure_type == FAILURE_TRANSIENT
        assert row.error_category == "timeout"
        assert row.attempt_count == 1
        assert row.next_retry_at is not None
        assert is_retry_eligible(row, now=row.next_retry_at - timedelta(seconds=1)) is False
        assert is_retry_eligible(row, now=row.next_retry_at + timedelta(seconds=1)) is True
        calls = {"n": 0}

        def ok(messages):
            import json

            calls["n"] += 1
            return json.dumps(_ok_body()), {"usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4}}

        row.next_retry_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=ok,
        )
        db.refresh(row)
        assert calls["n"] == 1
        assert row.status == "ready"
    finally:
        if db is not None:
            db.close()
        settings.asset_intelligence_mode = original


def test_retry_before_retry_after_suppressed(client):
    original = settings.asset_intelligence_mode
    db = None
    try:

        def boom(messages):
            raise httpx.ConnectError("nope")

        db, owner, product_id, image, row = _run_failing_job(
            boom, color=(22, 23, 24, 255), name="Connect Row"
        )
        assert row.failure_type == FAILURE_TRANSIENT
        calls = {"n": 0}

        def ok(messages):
            calls["n"] += 1
            raise AssertionError("should not call")

        row.next_retry_at = datetime.utcnow() + timedelta(minutes=4)
        db.commit()
        out = run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=ok,
        )
        assert calls["n"] == 0
        assert any(item.get("reason") == "retry_wait" for item in out["skipped"])
    finally:
        if db is not None:
            db.close()
        settings.asset_intelligence_mode = original


def test_max_attempts_stop_retries(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "Max Attempts")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((31, 32, 33, 255)))
        db.flush()
        row = ProductImageAnalysis(
            content_hash=image.content_hash,
            schema_version=SEMANTIC_SCHEMA_VERSION,
            model_version=analysis_model_version(),
            offering_context_version=offering_context_version(
                "unknown", category="test", description="d"
            ),
            status="failed",
            failure_type=FAILURE_TRANSIENT,
            error_category="timeout",
            attempt_count=MAX_ANALYSIS_ATTEMPTS,
            product_image_id=image.image_id,
        )
        row.owner_user_id = owner.user_id
        db.add(row)
        db.commit()
        calls = {"n": 0}

        def boom(messages):
            calls["n"] += 1
            raise httpx.TimeoutException("t")

        out = run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=boom,
        )
        assert calls["n"] == 0
        assert any(item.get("reason") == "max_attempts" for item in out["skipped"])
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_permanent_validation_does_not_retry_later(client):
    original = settings.asset_intelligence_mode
    db = None
    try:

        def always_bad(messages):
            return "not-json", {}

        db, owner, product_id, image, row = _run_failing_job(
            always_bad, color=(41, 42, 43, 255), name="Perm JSON"
        )
        assert row.failure_type == FAILURE_PERMANENT
        assert row.error_category == "structured_output_invalid"
        assert row.next_retry_at is None
        assert is_retry_eligible(row, now=datetime.utcnow() + timedelta(hours=2)) is False
        calls = {"n": 0}

        def ok(messages):
            calls["n"] += 1
            return "{}", {}

        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=ok,
        )
        assert calls["n"] == 0
    finally:
        if db is not None:
            db.close()
        settings.asset_intelligence_mode = original


def test_json_correction_includes_image_previous_output_and_errors():
    calls = []

    def complete(messages):
        calls.append(messages)
        if len(calls) == 1:
            return "THIS IS NOT JSON", {"usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}}
        import json

        return json.dumps(_ok_body()), {"usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}

    payload = analyze_reference_image(
        image_url="https://cdn.test/correct.png",
        offering_type="unknown",
        complete=complete,
    )
    assert len(calls) == 2
    assert payload["correction_used"] is True
    assert payload["request_count"] == 2
    assert payload["result"].asset_source_type == "product"
    second = calls[1][1]["content"]
    blob = str(second)
    assert "https://cdn.test/correct.png" in blob
    assert "THIS IS NOT JSON" in blob
    assert "Pydantic/JSON errors" in blob or "errors (capped)" in blob
    user_parts = second if isinstance(second, list) else []
    assert any(
        part.get("type") == "image_url"
        and (part.get("image_url") or {}).get("url") == "https://cdn.test/correct.png"
        for part in user_parts
    )
    assert payload["usage"]["prompt_tokens"] == 8
    assert payload["usage"]["completion_tokens"] == 3
    assert payload["usage"]["total_tokens"] == 11


def test_failed_correction_is_permanent_structured_invalid():
    def complete(messages):
        return "still-bad", {}

    try:
        analyze_reference_image(
            image_url="https://cdn.test/bad.png", offering_type="unknown", complete=complete
        )
        raise AssertionError("expected AnalysisFailure")
    except AnalysisFailure as exc:
        assert exc.failure_type == FAILURE_PERMANENT
        assert exc.error_category == "structured_output_invalid"
        assert exc.correction_used is True
        assert exc.request_count == 2


def test_maximum_one_correction_call():
    calls = {"n": 0}

    def complete(messages):
        calls["n"] += 1
        return "nope", {}

    try:
        analyze_reference_image(
            image_url="https://cdn.test/once.png", offering_type="unknown", complete=complete
        )
    except AnalysisFailure:
        pass
    assert calls["n"] == 2


def test_usage_aggregation_does_not_invent_tokens():
    merged = aggregate_usage(
        [
            {"prompt_tokens": 1, "completion_tokens": None, "total_tokens": 1},
            {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
        ],
        request_count=2,
        correction_used=True,
    )
    assert merged["prompt_tokens"] == 3
    assert merged["completion_tokens"] is None
    assert merged["total_tokens"] == 5
    assert merged["request_count"] == 2
    assert merged["correction_used"] is True
    missing_prompt = aggregate_usage(
        [{"prompt_tokens": None, "completion_tokens": 2, "total_tokens": 2}],
        request_count=1,
        correction_used=False,
    )
    assert missing_prompt["prompt_tokens"] is None
    assert missing_prompt["completion_tokens"] == 2


def test_https_only_image_urls():
    try:
        assert_analysis_image_url("http://cdn.test/a.png")
        raise AssertionError("expected reject")
    except AnalysisFailure as exc:
        assert exc.error_category == "unsupported_image_url"
    try:
        assert_analysis_image_url("https://127.0.0.1/a.png")
        raise AssertionError("expected reject")
    except AnalysisFailure as exc:
        assert exc.error_category == "unsupported_image_destination"
    assert assert_analysis_image_url("https://cdn.test/a.png").startswith("https://")


def test_unique_constraint_race_no_second_call(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "Race SKU")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((51, 52, 53, 255)))
        existing = ProductImageAnalysis(
            content_hash=image.content_hash,
            schema_version=SEMANTIC_SCHEMA_VERSION,
            model_version=analysis_model_version(),
            offering_context_version=offering_context_version(
                "unknown", category="test", description="d"
            ),
            status="ready",
            normalized_result=_ok_body(),
            product_image_id=image.image_id,
        )
        existing.owner_user_id = owner.user_id
        db.add(existing)
        db.commit()
        calls = {"n": 0}

        def boom(messages):
            calls["n"] += 1
            raise AssertionError("provider must not run")

        outcomes = {"processed": [], "skipped": [], "errors": []}
        product = db.query(Product).filter(Product.product_id == product_id).one()
        _analyze_one(
            db,
            image=image,
            product=product,
            owner_user_id=owner.user_id,
            offering="unknown",
            context=offering_context_for_product(product, "unknown"),
            existing=None,
            complete=boom,
            outcomes=outcomes,
        )
        assert calls["n"] == 0
        assert any(item.get("reason") in ("cache_hit", "unique_constraint_race") for item in outcomes["skipped"])
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_duplicate_active_job_skips_provider(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "Active Job")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((61, 62, 63, 255)))
        row = ProductImageAnalysis(
            content_hash=image.content_hash,
            schema_version=SEMANTIC_SCHEMA_VERSION,
            model_version=analysis_model_version(),
            offering_context_version=offering_context_version(
                "unknown", category="test", description="d"
            ),
            status="analyzing",
            last_attempt_at=datetime.utcnow(),
            attempt_count=1,
            product_image_id=image.image_id,
        )
        row.owner_user_id = owner.user_id
        db.add(row)
        db.commit()
        calls = {"n": 0}

        def boom(messages):
            calls["n"] += 1
            raise AssertionError("duplicate job")

        out = run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=boom,
        )
        assert calls["n"] == 0
        assert any(item.get("reason") == "already_scheduled" for item in out["skipped"])
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_generation_continues_after_permanent_and_transient(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "Continue Gen")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((71, 72, 73, 255)))
        db.commit()

        def boom(messages):
            raise httpx.TimeoutException("t")

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
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_rollout_off_and_cache_hit_zero_calls(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "off"
    try:
        assert enqueue_selected_intelligence(
            image_ids=["x"], owner_user_id="u", product_id="p", source="studio"
        ) == []
    finally:
        settings.asset_intelligence_mode = original
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "Hit Zero")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((81, 82, 83, 255)))
        db.commit()
        import json

        def ok(messages):
            return json.dumps(_ok_body()), {"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=ok,
        )
        calls = {"n": 0}

        def boom(messages):
            calls["n"] += 1
            raise AssertionError("cache hit")

        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=boom,
        )
        assert calls["n"] == 0
        assert is_usable_cache_hit(
            analysis_for_image(
                db,
                owner_user_id=owner.user_id,
                image=image,
                offering_type="unknown",
                product=db.query(Product).filter(Product.product_id == product_id).one(),
            )
        )
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_no_credits_or_byok_on_retry_path(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "No Credit")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((91, 92, 93, 255)))
        db.commit()
        with patch("bebcare.services.credit_grant_service.reserve_one") as reserve, patch(
            "bebcare.providers.registry.resolve_image_provider"
        ) as byok:
            run_intelligence_job(
                image_ids=[image.image_id],
                owner_user_id=owner.user_id,
                product_id=product_id,
                source="studio",
                complete=lambda messages: (__import__("json").dumps(_ok_body()), {}),
            )
            reserve.assert_not_called()
            byok.assert_not_called()
    finally:
        db.close()
        settings.asset_intelligence_mode = original


def test_schema_version_change_new_cache_identity(client):
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "studio"
    owner = _admin()
    product_id = _product(owner, "New Identity")
    db = SessionLocal()
    try:
        image = _image(db, product_id, _png((101, 102, 103, 255)))
        stale = ProductImageAnalysis(
            content_hash=image.content_hash,
            schema_version="sem_v0",
            model_version=analysis_model_version(),
            offering_context_version=offering_context_version(
                "unknown", category="test", description="d"
            ),
            status="failed",
            failure_type=FAILURE_PERMANENT,
            error_category="structured_output_invalid",
            attempt_count=3,
            product_image_id=image.image_id,
        )
        stale.owner_user_id = owner.user_id
        db.add(stale)
        db.commit()
        calls = {"n": 0}

        def ok(messages):
            import json

            calls["n"] += 1
            return json.dumps(_ok_body()), {}

        run_intelligence_job(
            image_ids=[image.image_id],
            owner_user_id=owner.user_id,
            product_id=product_id,
            source="studio",
            complete=ok,
        )
        assert calls["n"] == 1
    finally:
        db.close()
        settings.asset_intelligence_mode = original
