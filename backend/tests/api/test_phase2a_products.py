"""Phase 2A offering type and tenant isolation."""

from io import BytesIO
from unittest.mock import patch

from PIL import Image
from conftest import register_or_create_user

from bebcare.database import SessionLocal
from bebcare.models.product import ProductImage
from bebcare.models.user import User


def _png_file(name="a.png"):
    image = Image.new("RGBA", (24, 24), (10, 20, 30, 200))
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return name, buf, "image/png"


def _create_product(client, headers, name="Offering SKU"):
    brand = client.post("/v1/brands/", headers=headers, json={"name": f"{name} Brand"})
    assert brand.status_code in (200, 201)
    created = client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": name,
            "category": "test",
            "brand_id": brand.json()["brand_id"],
        },
    )
    assert created.status_code in (200, 201), created.text
    return created.json()


def test_offering_type_defaults_unknown_on_create(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "off_unk", "off_unk@test.local", "PassOffUnk123!"
    )
    body = _create_product(full_client, headers, "Unknown SKU")
    assert body["offering_type"] == "unknown"


def test_offering_type_optional_update_and_tenant_isolation(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "off_a", "off_a@test.local", "PassOffA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "off_b", "off_b@test.local", "PassOffB123!"
    )
    product = _create_product(full_client, headers_a, "Typed SKU")
    updated = full_client.put(
        f"/v1/products/{product['product_id']}",
        headers=headers_a,
        json={"offering_type": "saas"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["offering_type"] == "saas"
    denied = full_client.put(
        f"/v1/products/{product['product_id']}",
        headers=headers_b,
        json={"offering_type": "software"},
    )
    assert denied.status_code == 404
    invalid = full_client.put(
        f"/v1/products/{product['product_id']}",
        headers=headers_a,
        json={"offering_type": "not_a_type"},
    )
    assert invalid.status_code == 422


def test_upload_computes_metadata_without_github_when_mocked(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "up_meta", "up_meta@test.local", "PassUpMeta123!"
    )
    product = _create_product(full_client, headers, "Upload Meta")
    name, buf, mime = _png_file()
    with patch(
        "bebcare.api.product_routes.github_uploader.upload_file",
        return_value="https://cdn.jsdelivr.net/gh/test/repo@main/a.png",
    ), patch(
        "bebcare.api.product_routes.chroma_client.get_image_embedding",
        return_value=[0.0],
    ), patch(
        "bebcare.api.product_routes.chroma_client.add_image",
    ):
        resp = full_client.post(
            f"/v1/products/{product['product_id']}/images?image_type=product",
            headers=headers,
            files={"files": (name, buf, mime)},
        )
    assert resp.status_code == 200, resp.text
    image_id = resp.json()["uploaded"][0]["image_id"]
    db = SessionLocal()
    try:
        row = db.query(ProductImage).filter(ProductImage.image_id == image_id).one()
        assert row.analysis_status == "ready"
        assert row.content_hash
        assert row.has_alpha is True
        assert row.detected_mime_type == "image/png"
        owner = db.query(User).filter(User.username == "up_meta").one()
        other = ProductImage(
            product_id=product["product_id"],
            cdn_url="https://cdn.test/other.png",
            image_type="product",
            content_hash=row.content_hash,
            analysis_status="ready",
            deterministic_metadata_version=row.deterministic_metadata_version,
        )
        db.add(other)
        db.commit()
        assert owner.user_id
    finally:
        db.close()


def test_cross_tenant_cache_does_not_leak(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "hash_a", "hash_a@test.local", "PassHashA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "hash_b", "hash_b@test.local", "PassHashB123!"
    )
    product_a = _create_product(full_client, headers_a, "A Hash")
    product_b = _create_product(full_client, headers_b, "B Hash")
    from bebcare.services.asset_metadata import find_owner_cache_hit, refresh_deterministic_metadata
    from bebcare.services.deterministic_metadata import extract_deterministic_metadata

    raw = _png_file()[1].getvalue()
    extracted = extract_deterministic_metadata(raw)
    db = SessionLocal()
    try:
        user_a = db.query(User).filter(User.username == "hash_a").one()
        user_b = db.query(User).filter(User.username == "hash_b").one()
        img_a = ProductImage(
            product_id=product_a["product_id"],
            cdn_url="https://cdn.test/a.png",
            image_type="product",
        )
        img_b = ProductImage(
            product_id=product_b["product_id"],
            cdn_url="https://cdn.test/b.png",
            image_type="product",
        )
        db.add_all([img_a, img_b])
        db.flush()
        refresh_deterministic_metadata(
            db, img_a, owner_user_id=user_a.user_id, raw_bytes=raw, trigger="upload"
        )
        leaked = find_owner_cache_hit(
            db,
            owner_user_id=user_b.user_id,
            content_hash=extracted["content_hash"],
        )
        assert leaked is None
        refresh_deterministic_metadata(
            db, img_b, owner_user_id=user_b.user_id, raw_bytes=raw, trigger="upload"
        )
        assert img_b.analysis_status == "ready"
        assert (img_b.basic_quality_json or {}).get("processing", {}).get("cache_hit") is False
    finally:
        db.close()
