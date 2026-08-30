from datetime import datetime

from bebcare.database import SessionLocal
from bebcare.models.generation_run import GenerationRun
from bebcare.models.product import Product, ProductImage
from bebcare.models.user import User
from bebcare.schemas.reference_manifest import ReferenceManifest, assert_canonical_grounded_order
from bebcare.services.grounded_rollout import (
    EXECUTED_DETERMINISTIC,
    grounded_selection_enabled,
    grounded_rollout_mode,
)
from bebcare.services.preferred_image import set_preferred_image
from bebcare.utils.grounded_reference_selector import (
    InvalidReferencePinError,
    fallback_legacy_selection,
    select_grounded_references,
)
from bebcare.utils.reference_suitability import (
    aspect_penalty,
    is_near_duplicate,
    phash_bit_hamming,
    suitability_score,
)
import pytest


def _admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def _product_with_images(owner, images):
    db = SessionLocal()
    try:
        product = Product(
            product_name="Sel Product",
            category="test",
            description="d",
        )
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


def test_rollout_resolver_modes():
    from bebcare.config.settings import settings

    original = settings.grounded_rollout_mode
    try:
        settings.grounded_rollout_mode = "off"
        assert grounded_rollout_mode() == "off"
        assert grounded_selection_enabled(source="studio") is False
        assert grounded_selection_enabled(source="automation", task_mode="manual") is False

        settings.grounded_rollout_mode = "studio"
        assert grounded_selection_enabled(source="studio") is True
        assert grounded_selection_enabled(source="automation", task_mode="manual") is False

        settings.grounded_rollout_mode = "manual_automation"
        assert grounded_selection_enabled(source="studio") is True
        assert grounded_selection_enabled(source="automation", task_mode="manual") is True
        assert grounded_selection_enabled(source="automation", task_mode="auto") is False

        settings.grounded_rollout_mode = "all"
        assert grounded_selection_enabled(source="automation", task_mode="auto") is True
    finally:
        settings.grounded_rollout_mode = original


def test_preferred_product_wins_over_higher_score(client):
    owner = _admin()
    tiny = {"url": "https://cdn.test/tiny.jpg", "width": 200, "height": 200, "sort_index": 0}
    preferred = {
        "url": "https://cdn.test/pref.jpg",
        "width": 400,
        "height": 400,
        "is_preferred": True,
        "sort_index": 1,
        "phash": "aaaaaaaaaaaaaaaa",
    }
    huge = {
        "url": "https://cdn.test/huge.jpg",
        "width": 4000,
        "height": 4000,
        "sort_index": 2,
        "phash": "bbbbbbbbbbbbbbbb",
    }
    product_id, ids = _product_with_images(owner, [tiny, preferred, huge])
    db = SessionLocal()
    try:
        selected = select_grounded_references(
            db, product_id, 2, False, owner_user_id=owner.user_id, image_size="1440x2560"
        )
        manifest = ReferenceManifest.model_validate(selected.manifest)
        assert manifest.items[0].authority == "preferred"
        assert manifest.items[0].image_id == ids[1]
        assert_canonical_grounded_order(manifest)
    finally:
        db.close()


def test_preferred_scene_wins(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/p.jpg", "image_type": "product", "phash": "1111111111111111"},
            {
                "url": "https://cdn.test/s1.jpg",
                "image_type": "scene",
                "width": 4000,
                "height": 4000,
                "phash": "2222222222222222",
            },
            {
                "url": "https://cdn.test/s2.jpg",
                "image_type": "scene",
                "width": 800,
                "height": 800,
                "is_preferred": True,
                "phash": "3333333333333333",
            },
        ],
    )
    db = SessionLocal()
    try:
        selected = select_grounded_references(
            db, product_id, 1, True, owner_user_id=owner.user_id, image_size="1440x2560"
        )
        manifest = ReferenceManifest.model_validate(selected.manifest)
        scene = [i for i in manifest.items if i.role == "scene"][0]
        assert scene.authority == "preferred"
        assert scene.image_id == ids[2]
        assert manifest.items[-1].role == "scene"
    finally:
        db.close()


def test_invalid_preferred_ignored(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {
                "url": "https://cdn.test/bad.jpg",
                "width": 0,
                "height": 0,
                "is_preferred": True,
                "phash": "aaaaaaaaaaaaaaaa",
            },
            {
                "url": "https://cdn.test/ok.jpg",
                "width": 1200,
                "height": 1200,
                "phash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    db = SessionLocal()
    try:
        selected = select_grounded_references(
            db, product_id, 1, False, owner_user_id=owner.user_id
        )
        assert selected.manifest["items"][0]["image_id"] == ids[1]
        assert selected.manifest["items"][0]["authority"] != "preferred"
    finally:
        db.close()


def test_near_duplicates_excluded_from_supporting(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {
                "url": "https://cdn.test/a.jpg",
                "phash": "0000000000000000",
                "width": 1400,
                "height": 1400,
                "sort_index": 0,
            },
            {
                "url": "https://cdn.test/a-dup.jpg",
                "phash": "0000000000000001",
                "width": 1500,
                "height": 1500,
                "sort_index": 1,
            },
            {
                "url": "https://cdn.test/b.jpg",
                "phash": "ffffffffffffffff",
                "width": 1100,
                "height": 1100,
                "sort_index": 2,
            },
        ],
    )
    assert is_near_duplicate("0000000000000000", "0000000000000001")
    db = SessionLocal()
    try:
        selected = select_grounded_references(
            db, product_id, 3, False, owner_user_id=owner.user_id
        )
        support_ids = [
            i["image_id"] for i in selected.manifest["items"] if i["role"] == "supporting_subject"
        ]
        assert ids[1] not in support_ids
        assert ids[2] in support_ids
    finally:
        db.close()


def test_product_aspect_penalty_weaker_than_scene():
    product_pen = aspect_penalty(1000, 1000, 1440 / 2560, strong=False)
    scene_pen = aspect_penalty(1000, 1000, 1440 / 2560, strong=True)
    assert scene_pen > product_pen
    product_score = suitability_score(
        width=1000, height=1000, target_aspect=1440 / 2560, image_type="product", apply_diversity=False
    )
    scene_score = suitability_score(
        width=1000, height=1000, target_aspect=1440 / 2560, image_type="scene", apply_diversity=False
    )
    assert product_score > scene_score


def test_deterministic_ties_use_sort_index(client):
    owner = _admin()
    stamp = datetime.utcnow()
    product_id, ids = _product_with_images(
        owner,
        [
            {
                "url": "https://cdn.test/z.jpg",
                "width": 1200,
                "height": 1200,
                "phash": "aaaaaaaaaaaaaaaa",
                "sort_index": 2,
                "uploaded_at": stamp,
            },
            {
                "url": "https://cdn.test/a.jpg",
                "width": 1200,
                "height": 1200,
                "phash": "bbbbbbbbbbbbbbbb",
                "sort_index": 0,
                "uploaded_at": stamp,
            },
        ],
    )
    db = SessionLocal()
    try:
        first = select_grounded_references(
            db, product_id, 1, False, owner_user_id=owner.user_id
        )
        second = select_grounded_references(
            db, product_id, 1, False, owner_user_id=owner.user_id
        )
        assert first.manifest["items"][0]["image_id"] == ids[1]
        assert second.manifest["items"][0]["image_id"] == ids[1]
    finally:
        db.close()


def test_canonical_order_scene_last(client):
    owner = _admin()
    product_id, _ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/p1.jpg", "phash": "aaaaaaaaaaaaaaaa", "sort_index": 0},
            {"url": "https://cdn.test/p2.jpg", "phash": "bbbbbbbbbbbbbbbb", "sort_index": 1},
            {"url": "https://cdn.test/s.jpg", "image_type": "scene", "phash": "cccccccccccccccc"},
        ],
    )
    db = SessionLocal()
    try:
        selected = select_grounded_references(
            db, product_id, 2, True, owner_user_id=owner.user_id
        )
        roles = [i["role"] for i in selected.manifest["items"]]
        assert roles[0] == "primary_subject"
        assert roles[-1] == "scene"
        assert selected.reference_images[-1].endswith("s.jpg")
        assert_canonical_grounded_order(ReferenceManifest.model_validate(selected.manifest))
    finally:
        db.close()


def test_explicit_pin_rejects_other_owner(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner, [{"url": "https://cdn.test/p.jpg", "phash": "aaaaaaaaaaaaaaaa"}]
    )
    db = SessionLocal()
    try:
        with pytest.raises(InvalidReferencePinError):
            select_grounded_references(
                db,
                product_id,
                1,
                False,
                owner_user_id="not-the-owner",
                pinned_product_image_ids=ids,
            )
    finally:
        db.close()


def test_fallback_provenance_fields(client):
    owner = _admin()
    product_id, _ids = _product_with_images(
        owner, [{"url": "https://cdn.test/p.jpg", "phash": "aaaaaaaaaaaaaaaa"}]
    )
    db = SessionLocal()
    try:
        selected = fallback_legacy_selection(
            db, product_id, 1, False, reason="no_valid_product_references"
        )
        assert selected.requested_pipeline_version == "grounded_refs_v1"
        assert selected.executed_pipeline_version == "legacy_random_refs"
        assert selected.fallback_reason == "no_valid_product_references"
        assert selected.fallback_path == "legacy_random_refs"
    finally:
        db.close()


def test_diversity_does_not_override_preferred(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {
                "url": "https://cdn.test/pref.jpg",
                "is_preferred": True,
                "phash": "aaaaaaaaaaaaaaaa",
                "width": 800,
                "height": 800,
            },
            {
                "url": "https://cdn.test/other.jpg",
                "phash": "bbbbbbbbbbbbbbbb",
                "width": 4000,
                "height": 4000,
            },
        ],
    )
    db = SessionLocal()
    try:
        manifest = {
            "version": "ref_manifest_v1",
            "items": [
                {
                    "order": 1,
                    "role": "primary_subject",
                    "image_id": ids[0],
                    "cdn_url": "https://cdn.test/pref.jpg",
                    "image_type": "product",
                    "authority": "preferred",
                }
            ],
        }
        for _ in range(8):
            run = GenerationRun(
                source="studio",
                product_id=product_id,
                rollout_mode_at_start="studio",
                requested_pipeline_version="grounded_refs_v1",
                executed_pipeline_version=EXECUTED_DETERMINISTIC,
                reference_manifest=manifest,
                status="succeeded",
                credits_charged=0,
            )
            run.owner_user_id = owner.user_id
            db.add(run)
        db.commit()
        selected = select_grounded_references(
            db, product_id, 1, False, owner_user_id=owner.user_id
        )
        assert selected.manifest["items"][0]["image_id"] == ids[0]
        assert selected.manifest["items"][0]["authority"] == "preferred"
    finally:
        db.close()


def test_phash_threshold_is_configurable():
    assert phash_bit_hamming("0" * 16, "0" * 15 + "1") == 1


def test_set_preferred_clears_previous_same_type(client):
    owner = _admin()
    product_id, ids = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/a.jpg", "is_preferred": True, "phash": "aaaaaaaaaaaaaaaa"},
            {"url": "https://cdn.test/b.jpg", "phash": "bbbbbbbbbbbbbbbb"},
        ],
    )
    db = SessionLocal()
    try:
        second = db.query(ProductImage).filter(ProductImage.image_id == ids[1]).first()
        set_preferred_image(db, second, True)
        db.commit()
        first = db.query(ProductImage).filter(ProductImage.image_id == ids[0]).first()
        second = db.query(ProductImage).filter(ProductImage.image_id == ids[1]).first()
        assert first.is_preferred is False
        assert second.is_preferred is True
    finally:
        db.close()
