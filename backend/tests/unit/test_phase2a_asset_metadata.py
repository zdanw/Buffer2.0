"""Phase 2A deterministic asset metadata — no vision, no paid APIs."""

from io import BytesIO
from unittest.mock import patch

from PIL import Image

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.product import Product, ProductImage
from bebcare.models.user import User
from bebcare.services.asset_metadata import (
    DET_META_VERSION,
    STATUS_FAILED,
    STATUS_READY,
    STATUS_STALE,
    ensure_product_deterministic_metadata,
    find_owner_cache_hit,
    needs_deterministic_refresh,
    refresh_deterministic_metadata,
)
from bebcare.services.deterministic_metadata import (
    content_hash_bytes,
    extract_deterministic_metadata,
)
from bebcare.utils.reference_selector import resolve_generate_references


def _png_bytes(*, size=(32, 32), color=(255, 0, 0, 128), mode="RGBA") -> bytes:
    image = Image.new(mode, size, color if mode != "RGB" else color[:3])
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(*, size=(40, 20), orientation=None) -> bytes:
    image = Image.new("RGB", size, (0, 128, 255))
    buf = BytesIO()
    kwargs = {"format": "JPEG", "quality": 90}
    if orientation:
        exif = image.getexif()
        exif[274] = orientation
        kwargs["exif"] = exif
    image.save(buf, **kwargs)
    return buf.getvalue()


def _admin():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "admin").first()
    finally:
        db.close()


def _product(owner, name="Meta Product"):
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


def test_content_hash_is_deterministic():
    raw = _png_bytes()
    assert content_hash_bytes(raw) == content_hash_bytes(raw)
    assert content_hash_bytes(raw) != content_hash_bytes(_png_bytes(color=(0, 255, 0, 255)))


def test_mime_and_alpha_detection():
    png = extract_deterministic_metadata(_png_bytes())
    assert png["detected_mime_type"] == "image/png"
    assert png["has_alpha"] is True
    jpeg = extract_deterministic_metadata(_jpeg_bytes())
    assert jpeg["detected_mime_type"] == "image/jpeg"
    assert jpeg["has_alpha"] is False


def test_exif_orientation_does_not_mutate_original_bytes():
    original = _jpeg_bytes(size=(40, 20), orientation=6)
    snapshot = bytes(original)
    extracted = extract_deterministic_metadata(original)
    assert original == snapshot
    assert extracted["exif_orientation"] == 6
    assert extracted["width"] == 20
    assert extracted["height"] == 40


def test_offering_type_defaults_unknown(client):
    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        row = db.query(Product).filter(Product.product_id == product_id).one()
        assert row.offering_type == "unknown"
    finally:
        db.close()


def test_lifecycle_idempotent_and_stale(client):
    owner = _admin()
    product_id = _product(owner)
    raw = _png_bytes()
    db = SessionLocal()
    try:
        image = ProductImage(
            product_id=product_id,
            cdn_url="https://cdn.test/a.png",
            image_type="product",
            width=32,
            height=32,
        )
        db.add(image)
        db.flush()
        first = refresh_deterministic_metadata(
            db, image, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        assert first.analysis_status == STATUS_READY
        hash_one = first.content_hash
        at_one = first.deterministic_metadata_at
        second = refresh_deterministic_metadata(
            db, image, owner_user_id=owner.user_id, raw_bytes=raw, trigger="refresh"
        )
        assert second.content_hash == hash_one
        assert second.analysis_status == STATUS_READY
        assert (second.basic_quality_json or {}).get("processing", {}).get("cache_hit") is True
        image.deterministic_metadata_version = "det_meta_v0"
        db.flush()
        assert needs_deterministic_refresh(image) is True
        image.analysis_status = STATUS_STALE
        third = refresh_deterministic_metadata(
            db, image, owner_user_id=owner.user_id, raw_bytes=raw, trigger="refresh", force=True
        )
        assert third.deterministic_metadata_version == DET_META_VERSION
        assert third.analysis_status == STATUS_READY
        assert at_one is not None
    finally:
        db.close()


def test_exact_duplicate_reuses_owner_cache(client):
    owner = _admin()
    product_id = _product(owner)
    raw = _png_bytes()
    db = SessionLocal()
    try:
        first = ProductImage(
            product_id=product_id,
            cdn_url="https://cdn.test/a.png",
            image_type="product",
        )
        second = ProductImage(
            product_id=product_id,
            cdn_url="https://cdn.test/b.png",
            image_type="product",
        )
        db.add_all([first, second])
        db.flush()
        refresh_deterministic_metadata(
            db, first, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        refresh_deterministic_metadata(
            db, second, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        hit = find_owner_cache_hit(
            db,
            owner_user_id=owner.user_id,
            content_hash=first.content_hash,
            exclude_image_id=second.image_id,
        )
        assert hit is not None
        assert hit.image_id == first.image_id
        assert second.analysis_status == STATUS_READY
        assert (second.basic_quality_json or {}).get("processing", {}).get("cache_hit") is True
        assert first.image_id != second.image_id
    finally:
        db.close()


def test_near_duplicate_is_product_scoped(client):
    owner = _admin()
    a_id = _product(owner, "A")
    b_id = _product(owner, "B")
    raw = _png_bytes()
    db = SessionLocal()
    try:
        img_a = ProductImage(product_id=a_id, cdn_url="https://cdn.test/a.png", image_type="product")
        img_b = ProductImage(product_id=b_id, cdn_url="https://cdn.test/b.png", image_type="product")
        db.add_all([img_a, img_b])
        db.flush()
        refresh_deterministic_metadata(
            db, img_a, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        refresh_deterministic_metadata(
            db, img_b, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        assert img_a.near_duplicate_of_image_id is None
        assert img_b.near_duplicate_of_image_id is None
        twin = ProductImage(product_id=a_id, cdn_url="https://cdn.test/a2.png", image_type="product")
        db.add(twin)
        db.flush()
        refresh_deterministic_metadata(
            db, twin, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        assert twin.near_duplicate_of_image_id == img_a.image_id
        assert twin.near_duplicate_of_image_id != img_b.image_id
    finally:
        db.close()


def test_deletion_clears_near_duplicate_refs(client):
    owner = _admin()
    product_id = _product(owner)
    raw = _png_bytes()
    db = SessionLocal()
    try:
        first = ProductImage(
            product_id=product_id, cdn_url="https://cdn.test/a.png", image_type="product"
        )
        db.add(first)
        db.flush()
        refresh_deterministic_metadata(
            db, first, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        twin = ProductImage(
            product_id=product_id, cdn_url="https://cdn.test/b.png", image_type="product"
        )
        db.add(twin)
        db.flush()
        refresh_deterministic_metadata(
            db, twin, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
        )
        assert twin.near_duplicate_of_image_id == first.image_id
        from bebcare.services.asset_metadata import clear_near_duplicate_refs

        clear_near_duplicate_refs(db, first.image_id)
        db.delete(first)
        db.commit()
        leftover = db.query(ProductImage).filter(ProductImage.image_id == twin.image_id).one()
        assert leftover.near_duplicate_of_image_id is None
        db.commit()
    finally:
        db.close()


def test_legacy_lazy_processing_tolerates_cdn_failure(client):
    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        image = ProductImage(
            product_id=product_id,
            cdn_url="https://cdn.test/missing.png",
            image_type="product",
            width=800,
            height=800,
        )
        db.add(image)
        db.flush()
        ensure_product_deterministic_metadata(
            db, product_id=product_id, owner_user_id=owner.user_id, trigger="generate"
        )
        db.refresh(image)
        assert image.analysis_status in (STATUS_FAILED, "partial")
        selected = resolve_generate_references(
            db,
            product_id=product_id,
            owner_user_id=owner.user_id,
            reference_count=1,
            use_scene_reference=False,
            source="studio",
        )
        assert selected.reference_images
        assert selected.deterministic_metadata is not None
        assert needs_deterministic_refresh(image) is False
    finally:
        db.commit()
        db.close()


def test_metadata_failure_does_not_block_generation(client):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "off"
    owner = _admin()
    product_id = _product(owner)
    db = SessionLocal()
    try:
        image = ProductImage(
            product_id=product_id,
            cdn_url="https://cdn.test/p.jpg",
            image_type="product",
            width=1200,
            height=1200,
        )
        db.add(image)
        db.commit()
        with patch(
            "bebcare.services.asset_metadata.refresh_deterministic_metadata",
            side_effect=RuntimeError("boom"),
        ):
            selected = resolve_generate_references(
                db,
                product_id=product_id,
                owner_user_id=owner.user_id,
                reference_count=1,
                use_scene_reference=False,
                source="studio",
            )
        assert selected.executed_pipeline_version == "legacy_random_refs"
        assert selected.reference_images
    finally:
        settings.grounded_rollout_mode = original
        db.close()


def test_no_external_provider_called_for_local_bytes(client):
    owner = _admin()
    product_id = _product(owner)
    raw = _png_bytes()
    db = SessionLocal()
    try:
        image = ProductImage(
            product_id=product_id, cdn_url="https://cdn.test/local.png", image_type="product"
        )
        db.add(image)
        db.flush()
        with patch("requests.get") as get:
            refresh_deterministic_metadata(
                db, image, owner_user_id=owner.user_id, raw_bytes=raw, trigger="upload"
            )
            get.assert_not_called()
        assert image.analysis_status == STATUS_READY
    finally:
        db.close()
