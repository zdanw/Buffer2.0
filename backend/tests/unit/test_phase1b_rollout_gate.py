"""Client experiment_variant must not bypass GROUNDED_ROLLOUT_MODE."""

from datetime import datetime
from unittest.mock import patch

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.generator.content_generator import ContentGenerator
from bebcare.models.product import Product, ProductImage
from bebcare.models.user import User
from bebcare.providers.generate_request import GenerateImageRequest
from bebcare.services.grounded_rollout import (
    EXPERIMENT_BASELINE,
    EXECUTED_GROUNDED_PROMPT_TRANSPORT,
    EXECUTED_GROUNDED_PROMPT_V1,
    EXECUTED_LEGACY_RANDOM,
    grounded_prompt_contract_enabled,
    grounded_role_transport_enabled,
    selection_provenance,
)
from bebcare.utils.reference_selector import resolve_generate_references


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
            product_name="Gate Product",
            category="test",
            description="d",
        )
        product.owner_user_id = owner.user_id
        db.add(product)
        db.flush()
        for spec in images:
            db.add(
                ProductImage(
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
            )
        db.commit()
        return product.product_id
    finally:
        db.close()


def _info_from_selection(selected, *, source="studio"):
    provenance = selection_provenance(selected, source=source)
    return {
        "experiment_variant": selected.experiment_variant,
        "executed_pipeline_version": selected.executed_pipeline_version,
        "grounded_phase1b_enabled": bool(selected.grounded),
        "generation_provenance": provenance,
        "locale": "en",
    }


def _resolve(db, product_id, owner_id, *, source, task_mode=None, requested=None):
    return resolve_generate_references(
        db,
        product_id=product_id,
        owner_user_id=owner_id,
        reference_count=1,
        use_scene_reference=True,
        source=source,
        task_mode=task_mode,
        requested_experiment=requested,
    )


def test_a_rollout_off_transport_variant_stays_baseline(client):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "off"
    owner = _admin()
    product_id = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/p.jpg", "phash": "aaaaaaaaaaaaaaaa"},
            {
                "url": "https://cdn.test/s.jpg",
                "image_type": "scene",
                "phash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    db = SessionLocal()
    try:
        selected = _resolve(
            db,
            product_id,
            owner.user_id,
            source="studio",
            requested="grounded_prompt_role_transport_v1",
        )
        assert selected.grounded is False
        assert selected.experiment_variant == EXPERIMENT_BASELINE
        assert selected.executed_pipeline_version == EXECUTED_LEGACY_RANDOM
        assert selected.requested_pipeline_version == "baseline_current"
        assert selected.requested_experiment_variant == "grounded_prompt_role_transport_v1"
        roles = [item["role"] for item in selected.manifest["items"]]
        assert roles[0] == "scene"
        info = _info_from_selection(selected)
        assert grounded_prompt_contract_enabled(info) is False
        assert grounded_role_transport_enabled(info) is False
        prompt = ContentGenerator()._vision_scene_system_prompt(info)
        assert "hand-held replacement" in prompt
        assert "Handheld physical-product replacement is prohibited" not in prompt
        assert "Image 1 is the primary subject" not in prompt
        req = GenerateImageRequest.from_legacy(
            "redraw",
            None,
            "1024x1024",
            "m",
            selected.reference_images,
            annotate_roles=grounded_role_transport_enabled(info),
        )
        assert "Image 1" not in req.prompt_with_role_labels()
    finally:
        settings.grounded_rollout_mode = original
        db.close()


def test_b_rollout_off_prompt_v1_variant_stays_baseline(client):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "off"
    owner = _admin()
    product_id = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/p.jpg", "phash": "aaaaaaaaaaaaaaaa"},
            {
                "url": "https://cdn.test/s.jpg",
                "image_type": "scene",
                "phash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    db = SessionLocal()
    try:
        selected = _resolve(
            db,
            product_id,
            owner.user_id,
            source="studio",
            requested="grounded_prompt_v1",
        )
        assert selected.grounded is False
        assert selected.executed_pipeline_version == EXECUTED_LEGACY_RANDOM
        info = _info_from_selection(selected)
        assert grounded_prompt_contract_enabled(info) is False
        assert grounded_role_transport_enabled(info) is False
        prompt = ContentGenerator()._vision_scene_system_prompt(info)
        assert "hand-held replacement" in prompt
    finally:
        settings.grounded_rollout_mode = original
        db.close()


def test_c_studio_mode_studio_source_allowed_variant(client):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "studio"
    owner = _admin()
    product_id = _product_with_images(
        owner,
        [
            {
                "url": "https://cdn.test/p.jpg",
                "phash": "aaaaaaaaaaaaaaaa",
                "is_preferred": True,
            },
            {
                "url": "https://cdn.test/s.jpg",
                "image_type": "scene",
                "phash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    db = SessionLocal()
    try:
        selected = _resolve(
            db,
            product_id,
            owner.user_id,
            source="studio",
            requested="grounded_prompt_role_transport_v1",
        )
        assert selected.grounded is True
        assert selected.experiment_variant == "grounded_prompt_role_transport_v1"
        assert selected.executed_pipeline_version == EXECUTED_GROUNDED_PROMPT_TRANSPORT
        assert selected.requested_pipeline_version == "grounded_refs_v1"
        roles = [item["role"] for item in selected.manifest["items"]]
        assert roles[0] == "primary_subject"
        assert roles[-1] == "scene"
        info = _info_from_selection(selected)
        assert grounded_prompt_contract_enabled(info) is True
        assert grounded_role_transport_enabled(info) is True
        prompt = ContentGenerator()._vision_scene_system_prompt(info)
        assert "Handheld physical-product replacement is prohibited" in prompt
        assert "hand-held replacement" not in prompt

        v1 = _resolve(
            db,
            product_id,
            owner.user_id,
            source="studio",
            requested="grounded_prompt_v1",
        )
        assert v1.executed_pipeline_version == EXECUTED_GROUNDED_PROMPT_V1
        v1_info = _info_from_selection(v1)
        assert grounded_prompt_contract_enabled(v1_info) is True
        assert grounded_role_transport_enabled(v1_info) is False
    finally:
        settings.grounded_rollout_mode = original
        db.close()


def test_d_studio_mode_automation_source_no_bypass(client):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "studio"
    owner = _admin()
    product_id = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/p.jpg", "phash": "aaaaaaaaaaaaaaaa"},
            {
                "url": "https://cdn.test/s.jpg",
                "image_type": "scene",
                "phash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    db = SessionLocal()
    try:
        selected = _resolve(
            db,
            product_id,
            owner.user_id,
            source="automation",
            task_mode="automatic",
            requested="grounded_prompt_role_transport_v1",
        )
        assert selected.grounded is False
        assert selected.executed_pipeline_version == EXECUTED_LEGACY_RANDOM
        assert selected.experiment_variant == EXPERIMENT_BASELINE
        info = _info_from_selection(selected, source="automation")
        assert grounded_prompt_contract_enabled(info) is False
        assert grounded_role_transport_enabled(info) is False
    finally:
        settings.grounded_rollout_mode = original
        db.close()


def test_e_invalid_experiment_variant_does_not_enable(client):
    original = settings.grounded_rollout_mode
    owner = _admin()
    product_id = _product_with_images(
        owner,
        [
            {
                "url": "https://cdn.test/p.jpg",
                "phash": "aaaaaaaaaaaaaaaa",
                "is_preferred": True,
            },
            {
                "url": "https://cdn.test/s.jpg",
                "image_type": "scene",
                "phash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    db = SessionLocal()
    try:
        settings.grounded_rollout_mode = "off"
        off = _resolve(
            db,
            product_id,
            owner.user_id,
            source="studio",
            requested="not_a_real_variant",
        )
        assert off.grounded is False
        assert off.executed_pipeline_version == EXECUTED_LEGACY_RANDOM
        assert grounded_prompt_contract_enabled(_info_from_selection(off)) is False

        settings.grounded_rollout_mode = "studio"
        on = _resolve(
            db,
            product_id,
            owner.user_id,
            source="studio",
            requested="not_a_real_variant",
        )
        assert on.grounded is True
        assert on.requested_experiment_variant == "not_a_real_variant"
        assert on.experiment_variant == "grounded_prompt_role_transport_v1"
        assert on.executed_pipeline_version == EXECUTED_GROUNDED_PROMPT_TRANSPORT
    finally:
        settings.grounded_rollout_mode = original
        db.close()


def test_f_selector_fallback_does_not_apply_phase1b_contract(client):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "studio"
    owner = _admin()
    product_id = _product_with_images(
        owner,
        [
            {"url": "https://cdn.test/p.jpg", "phash": "aaaaaaaaaaaaaaaa"},
            {
                "url": "https://cdn.test/s.jpg",
                "image_type": "scene",
                "phash": "bbbbbbbbbbbbbbbb",
            },
        ],
    )
    db = SessionLocal()
    try:
        with patch(
            "bebcare.utils.grounded_reference_selector.select_grounded_references",
            side_effect=RuntimeError("selector exploded"),
        ):
            selected = _resolve(
                db,
                product_id,
                owner.user_id,
                source="studio",
                requested="grounded_prompt_role_transport_v1",
            )
        assert selected.grounded is False
        assert selected.requested_pipeline_version == "grounded_refs_v1"
        assert selected.executed_pipeline_version == EXECUTED_LEGACY_RANDOM
        assert selected.experiment_variant != "grounded_prompt_role_transport_v1"
        assert selected.requested_experiment_variant == "grounded_prompt_role_transport_v1"
        info = _info_from_selection(selected)
        assert info["generation_provenance"]["grounded_phase1b_enabled"] is False
        assert grounded_prompt_contract_enabled(info) is False
        assert grounded_role_transport_enabled(info) is False
    finally:
        settings.grounded_rollout_mode = original
        db.close()


def test_client_experiment_alone_does_not_enable_contract():
    spoofed = {
        "experiment_variant": "grounded_prompt_role_transport_v1",
        "executed_pipeline_version": "grounded_prompt_role_transport_v1",
        "grounded_phase1b_enabled": False,
        "generation_provenance": {
            "experiment_variant": "grounded_prompt_role_transport_v1",
            "executed_pipeline_version": "grounded_prompt_role_transport_v1",
            "grounded_phase1b_enabled": False,
            "requested_experiment_variant": "grounded_prompt_role_transport_v1",
        },
    }
    assert grounded_prompt_contract_enabled(spoofed) is False
    assert grounded_role_transport_enabled(spoofed) is False
