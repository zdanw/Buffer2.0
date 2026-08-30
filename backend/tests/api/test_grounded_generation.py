"""Studio grounded GenerationRun provenance, compare pinning, tenant isolation."""

from unittest.mock import AsyncMock, patch

from bebcare.config.settings import settings
from bebcare.database import SessionLocal
from bebcare.models.generation_run import GenerationArtifact, GenerationRun
from bebcare.models.image_credit import ImageCreditReservation
from bebcare.models.product import ProductImage
from conftest import register_or_create_user

_PROVIDER_BODY = {
    "name": "Phase1A Doubao",
    "provider_type": "doubao_ark",
    "base_url": "https://ark.example.invalid",
    "api_key": "sk-test-not-a-real-key",
    "supports_list_models": False,
    "is_default": True,
}


def _create_product(client, headers, name):
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
    assert created.status_code in (200, 201)
    return created.json()["product_id"]


def _add_images(product_id, specs):
    db = SessionLocal()
    try:
        ids = []
        for spec in specs:
            row = ProductImage(
                product_id=product_id,
                cdn_url=spec["url"],
                phash=spec.get("phash", "aaaaaaaaaaaaaaaa"),
                width=spec.get("width", 1200),
                height=spec.get("height", 1200),
                image_type=spec.get("image_type", "product"),
                is_preferred=spec.get("is_preferred", False),
                sort_index=spec.get("sort_index", 0),
            )
            db.add(row)
            db.flush()
            ids.append(row.image_id)
        db.commit()
        return ids
    finally:
        db.close()


def _create_provider(client, headers):
    resp = client.post("/v1/image-providers/", headers=headers, json=_PROVIDER_BODY)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_studio_grounded_run_writes_manifest_and_artifact(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "studio"
    try:
        headers = register_or_create_user(
            full_client, auth_headers, "g1a_run", "g1a_run@test.local", "PassG1aRun123!"
        )
        product_id = _create_product(full_client, headers, "Grounded SKU")
        image_ids = _add_images(
            product_id,
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
        provider_id = _create_provider(full_client, headers)
        with patch(
            "bebcare.api.generate_routes.ContentGenerator.generate_image_async",
            new_callable=AsyncMock,
            return_value={
                "image_urls": ["https://cdn.test/out.jpg"],
                "warning": "cdn slow",
            },
        ):
            resp = full_client.post(
                "/v1/generate/image/",
                headers=headers,
                json={
                    "product_id": product_id,
                    "platform": "instagram",
                    "image_provider_mode": "byok",
                    "image_provider_id": provider_id,
                    "use_scene_reference": True,
                    "reference_count": 1,
                },
            )
        assert resp.status_code == 200, resp.text
        task_id = resp.json()["task_id"]
        status = full_client.get(f"/v1/generate/status/{task_id}", headers=headers)
        assert status.status_code == 200
        assert status.json()["status"] == "SUCCESS"

        db = SessionLocal()
        try:
            run = (
                db.query(GenerationRun)
                .filter(GenerationRun.generate_task_id == task_id)
                .one()
            )
            assert run.source == "studio"
            assert run.rollout_mode_at_start == "studio"
            assert run.requested_pipeline_version == "grounded_refs_v1"
            assert run.executed_pipeline_version == "grounded_prompt_role_transport_v1"
            assert run.generation_plan
            items = (run.reference_manifest or {}).get("items") or []
            assert items
            assert items[0]["role"] == "primary_subject"
            assert items[0]["image_id"] == image_ids[0]
            assert items[0]["authority"] == "preferred"
            assert items[-1]["role"] == "scene"
            assert run.generation_plan["display_configuration"] == run.generation_plan["display_config"]
            assert run.generation_plan["subject"]["physical_instance_limit"] is None
            assert run.generation_plan["subject_spec"]["primary_subject_count"] == 1
            assert run.generation_plan["reference_manifest"]["items"][0]["role"] == items[0]["role"]
            artifacts = (
                db.query(GenerationArtifact)
                .filter(GenerationArtifact.run_id == run.run_id)
                .all()
            )
            assert len(artifacts) == 1
            assert artifacts[0].cdn_url == "https://cdn.test/out.jpg"
            assert artifacts[0].persistence_warning == "cdn slow"
            assert artifacts[0].owner_user_id == run.owner_user_id
        finally:
            db.close()
    finally:
        settings.grounded_rollout_mode = original


def test_compare_jobs_share_group_and_manifest(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "studio"
    try:
        headers = register_or_create_user(
            full_client, auth_headers, "g1a_cmp", "g1a_cmp@test.local", "PassG1aCmp123!"
        )
        product_id = _create_product(full_client, headers, "Compare SKU")
        image_ids = _add_images(
            product_id,
            [
                {"url": "https://cdn.test/p.jpg", "phash": "aaaaaaaaaaaaaaaa"},
                {"url": "https://cdn.test/s.jpg", "image_type": "scene", "phash": "bbbbbbbbbbbbbbbb"},
            ],
        )
        provider_id = _create_provider(full_client, headers)
        group_id = "compare-group-phase1a"
        payload = {
            "product_id": product_id,
            "platform": "instagram",
            "image_provider_mode": "byok",
            "image_provider_id": provider_id,
            "use_scene_reference": True,
            "reference_count": 1,
            "reference_product_image_ids": [image_ids[0]],
            "reference_scene_image_ids": [image_ids[1]],
            "compare_group_id": group_id,
        }
        with patch(
            "bebcare.api.generate_routes.ContentGenerator.generate_image_async",
            new_callable=AsyncMock,
            return_value={"image_urls": ["https://cdn.test/out.jpg"]},
        ):
            legacy = full_client.post(
                "/v1/generate/image/",
                headers=headers,
                json={**payload, "image_prompt_pipeline": "legacy_scene"},
            )
            vision = full_client.post(
                "/v1/generate/image/",
                headers=headers,
                json={**payload, "image_prompt_pipeline": "vision_scene"},
            )
        assert legacy.status_code == 200, legacy.text
        assert vision.status_code == 200, vision.text
        db = SessionLocal()
        try:
            runs = (
                db.query(GenerationRun)
                .filter(GenerationRun.compare_group_id == group_id)
                .all()
            )
            assert len(runs) == 2
            manifests = [run.reference_manifest for run in runs]
            assert manifests[0] == manifests[1]
            assert {run.image_prompt_pipeline for run in runs} == {
                "legacy_scene",
                "vision_scene",
            }
            select = full_client.post(
                "/v1/generate/compare-selection/",
                headers=headers,
                json={
                    "compare_group_id": group_id,
                    "image_prompt_pipeline": "vision_scene",
                },
            )
            assert select.status_code == 200, select.text
            db.expire_all()
            runs = (
                db.query(GenerationRun)
                .filter(GenerationRun.compare_group_id == group_id)
                .all()
            )
            selected_pipelines = {
                run.image_prompt_pipeline
                for run in runs
                if any(art.selected for art in run.artifacts)
            }
            assert selected_pipelines == {"vision_scene"}
        finally:
            db.close()
    finally:
        settings.grounded_rollout_mode = original


def test_platform_compare_reserves_two_credits(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "off"
    try:
        headers = register_or_create_user(
            full_client, auth_headers, "g1a_cred", "g1a_cred@test.local", "PassG1aCred123!"
        )
        product_id = _create_product(full_client, headers, "Credit SKU")
        _add_images(product_id, [{"url": "https://cdn.test/p.jpg"}])
        with patch(
            "bebcare.api.generate_routes._require_image_provider"
        ), patch(
            "bebcare.providers.registry.resolve_system_image_provider",
            return_value=object(),
        ), patch(
            "bebcare.api.generate_routes.ContentGenerator.generate_image_async",
            new_callable=AsyncMock,
            return_value={"image_urls": ["https://cdn.test/out.jpg"]},
        ):
            a = full_client.post(
                "/v1/generate/image/",
                headers=headers,
                json={
                    "product_id": product_id,
                    "platform": "instagram",
                    "image_provider_mode": "platform",
                    "compare_group_id": "credits-two",
                },
            )
            b = full_client.post(
                "/v1/generate/image/",
                headers=headers,
                json={
                    "product_id": product_id,
                    "platform": "instagram",
                    "image_provider_mode": "platform",
                    "compare_group_id": "credits-two",
                },
            )
        assert a.status_code == 200, a.text
        assert b.status_code == 200, b.text
        db = SessionLocal()
        try:
            n = db.query(ImageCreditReservation).filter(
                ImageCreditReservation.generate_task_id.in_(
                    [a.json()["task_id"], b.json()["task_id"]]
                )
            ).count()
            assert n == 2
        finally:
            db.close()
    finally:
        settings.grounded_rollout_mode = original


def test_rollout_off_uses_legacy_pipeline_version(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "off"
    try:
        headers = register_or_create_user(
            full_client, auth_headers, "g1a_off", "g1a_off@test.local", "PassG1aOff123!"
        )
        product_id = _create_product(full_client, headers, "Off SKU")
        _add_images(product_id, [{"url": "https://cdn.test/p.jpg"}])
        provider_id = _create_provider(full_client, headers)
        with patch(
            "bebcare.api.generate_routes.ContentGenerator.generate_image_async",
            new_callable=AsyncMock,
            return_value={"image_urls": ["https://cdn.test/out.jpg"]},
        ):
            resp = full_client.post(
                "/v1/generate/image/",
                headers=headers,
                json={
                    "product_id": product_id,
                    "platform": "instagram",
                    "image_provider_mode": "byok",
                    "image_provider_id": provider_id,
                },
            )
        assert resp.status_code == 200, resp.text
        db = SessionLocal()
        try:
            run = (
                db.query(GenerationRun)
                .filter(GenerationRun.generate_task_id == resp.json()["task_id"])
                .one()
            )
            assert run.requested_pipeline_version == "baseline_current"
            assert run.executed_pipeline_version == "legacy_random_refs"
            assert run.fallback_reason is None
            assert run.generation_plan is None
        finally:
            db.close()
    finally:
        settings.grounded_rollout_mode = original


def _post_generate_capturing(full_client, headers, payload):
    captured = {}

    async def _fake(self, product_info, *args, **kwargs):
        captured["product_info"] = product_info
        return {"image_urls": ["https://cdn.test/out.jpg"]}

    with patch(
        "bebcare.api.generate_routes.ContentGenerator.generate_image_async",
        new=_fake,
    ):
        resp = full_client.post(
            "/v1/generate/image/",
            headers=headers,
            json=payload,
        )
    return resp, captured


def test_rollout_off_ignores_grounded_transport_experiment(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "off"
    try:
        headers = register_or_create_user(
            full_client, auth_headers, "g1b_off_t", "g1b_off_t@test.local", "PassG1bOffT123!"
        )
        product_id = _create_product(full_client, headers, "Off Transport SKU")
        _add_images(
            product_id,
            [
                {"url": "https://cdn.test/p.jpg"},
                {"url": "https://cdn.test/s.jpg", "image_type": "scene"},
            ],
        )
        provider_id = _create_provider(full_client, headers)
        resp, captured = _post_generate_capturing(
            full_client,
            headers,
            {
                "product_id": product_id,
                "platform": "instagram",
                "image_provider_mode": "byok",
                "image_provider_id": provider_id,
                "use_scene_reference": True,
                "experiment_variant": "grounded_prompt_role_transport_v1",
            },
        )
        assert resp.status_code == 200, resp.text
        info = captured["product_info"]
        from bebcare.services.grounded_rollout import (
            grounded_prompt_contract_enabled,
            grounded_role_transport_enabled,
        )

        assert info["grounded_phase1b_enabled"] is False
        assert grounded_prompt_contract_enabled(info) is False
        assert grounded_role_transport_enabled(info) is False
        assert info["experiment_variant"] == "baseline_current"
        roles = [
            item["role"]
            for item in (info["generation_provenance"]["reference_manifest"]["items"])
        ]
        assert roles[0] == "scene"
        db = SessionLocal()
        try:
            run = (
                db.query(GenerationRun)
                .filter(GenerationRun.generate_task_id == resp.json()["task_id"])
                .one()
            )
            assert run.requested_pipeline_version == "baseline_current"
            assert run.executed_pipeline_version == "legacy_random_refs"
            assert run.experiment_variant == "baseline_current"
            assert run.generation_plan is None
            assert (
                info["generation_provenance"].get("requested_experiment_variant")
                == "grounded_prompt_role_transport_v1"
            )
        finally:
            db.close()
    finally:
        settings.grounded_rollout_mode = original


def test_rollout_off_ignores_grounded_prompt_v1_experiment(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "off"
    try:
        headers = register_or_create_user(
            full_client, auth_headers, "g1b_off_v1", "g1b_off_v1@test.local", "PassG1bOffV1123!"
        )
        product_id = _create_product(full_client, headers, "Off V1 SKU")
        _add_images(product_id, [{"url": "https://cdn.test/p.jpg"}])
        provider_id = _create_provider(full_client, headers)
        resp, captured = _post_generate_capturing(
            full_client,
            headers,
            {
                "product_id": product_id,
                "platform": "instagram",
                "image_provider_mode": "byok",
                "image_provider_id": provider_id,
                "experiment_variant": "grounded_prompt_v1",
            },
        )
        assert resp.status_code == 200, resp.text
        from bebcare.services.grounded_rollout import grounded_prompt_contract_enabled

        assert grounded_prompt_contract_enabled(captured["product_info"]) is False
        db = SessionLocal()
        try:
            run = (
                db.query(GenerationRun)
                .filter(GenerationRun.generate_task_id == resp.json()["task_id"])
                .one()
            )
            assert run.executed_pipeline_version == "legacy_random_refs"
            assert run.experiment_variant == "baseline_current"
            assert run.generation_plan is None
        finally:
            db.close()
    finally:
        settings.grounded_rollout_mode = original


def test_studio_mode_pins_allowed_grounded_variant(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "studio"
    try:
        headers = register_or_create_user(
            full_client, auth_headers, "g1b_pin", "g1b_pin@test.local", "PassG1bPin123!"
        )
        product_id = _create_product(full_client, headers, "Pin SKU")
        _add_images(
            product_id,
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
        provider_id = _create_provider(full_client, headers)
        payload = {
            "product_id": product_id,
            "platform": "instagram",
            "image_provider_mode": "byok",
            "image_provider_id": provider_id,
            "use_scene_reference": True,
            "reference_count": 1,
        }
        transport, captured_t = _post_generate_capturing(
            full_client,
            headers,
            {**payload, "experiment_variant": "grounded_prompt_role_transport_v1"},
        )
        v1, captured_v = _post_generate_capturing(
            full_client,
            headers,
            {**payload, "experiment_variant": "grounded_prompt_v1"},
        )
        assert transport.status_code == 200, transport.text
        assert v1.status_code == 200, v1.text
        from bebcare.services.grounded_rollout import (
            grounded_prompt_contract_enabled,
            grounded_role_transport_enabled,
        )

        assert captured_t["product_info"]["grounded_phase1b_enabled"] is True
        assert grounded_prompt_contract_enabled(captured_t["product_info"]) is True
        assert grounded_role_transport_enabled(captured_t["product_info"]) is True
        roles = [
            item["role"]
            for item in captured_t["product_info"]["generation_provenance"][
                "reference_manifest"
            ]["items"]
        ]
        assert roles[0] == "primary_subject"
        assert roles[-1] == "scene"
        assert grounded_role_transport_enabled(captured_v["product_info"]) is False
        db = SessionLocal()
        try:
            t_run = (
                db.query(GenerationRun)
                .filter(GenerationRun.generate_task_id == transport.json()["task_id"])
                .one()
            )
            v_run = (
                db.query(GenerationRun)
                .filter(GenerationRun.generate_task_id == v1.json()["task_id"])
                .one()
            )
            assert t_run.executed_pipeline_version == "grounded_prompt_role_transport_v1"
            assert v_run.executed_pipeline_version == "grounded_prompt_v1"
        finally:
            db.close()
    finally:
        settings.grounded_rollout_mode = original


def test_preferred_patch_tenant_isolation(full_client, auth_headers):
    headers_a = register_or_create_user(
        full_client, auth_headers, "pref_a", "pref_a@test.local", "PassPrefA123!"
    )
    headers_b = register_or_create_user(
        full_client, auth_headers, "pref_b", "pref_b@test.local", "PassPrefB123!"
    )
    product_id = _create_product(full_client, headers_a, "Pref Product")
    ids = _add_images(product_id, [{"url": "https://cdn.test/p.jpg"}])
    denied = full_client.patch(
        f"/v1/products/{product_id}/images/{ids[0]}",
        headers=headers_b,
        json={"is_preferred": True},
    )
    assert denied.status_code in (403, 404)
    ok = full_client.patch(
        f"/v1/products/{product_id}/images/{ids[0]}",
        headers=headers_a,
        json={"is_preferred": True},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["is_preferred"] is True
    scene_ids = _add_images(
        product_id, [{"url": "https://cdn.test/s.jpg", "image_type": "scene"}]
    )
    scene_ok = full_client.patch(
        f"/v1/products/{product_id}/images/{scene_ids[0]}",
        headers=headers_a,
        json={"is_preferred": True},
    )
    assert scene_ok.status_code == 200
    product_still = full_client.get(f"/v1/products/{product_id}", headers=headers_a)
    body = product_still.json()
    assert len([i for i in body.get("product_images", []) if i.get("is_preferred")]) == 1
    assert len([i for i in body.get("scene_images", []) if i.get("is_preferred")]) == 1


def test_pin_rejects_other_tenant_image_id(full_client, auth_headers):
    original = settings.grounded_rollout_mode
    settings.grounded_rollout_mode = "studio"
    try:
        headers_a = register_or_create_user(
            full_client, auth_headers, "pin_a", "pin_a@test.local", "PassPinA123!"
        )
        headers_b = register_or_create_user(
            full_client, auth_headers, "pin_b", "pin_b@test.local", "PassPinB123!"
        )
        product_a = _create_product(full_client, headers_a, "A Pins")
        product_b = _create_product(full_client, headers_b, "B Pins")
        ids_a = _add_images(product_a, [{"url": "https://cdn.test/a.jpg"}])
        provider_b = _create_provider(full_client, headers_b)
        resp = full_client.post(
            "/v1/generate/image/",
            headers=headers_b,
            json={
                "product_id": product_b,
                "platform": "instagram",
                "image_provider_mode": "byok",
                "image_provider_id": provider_b,
                "reference_product_image_ids": ids_a,
            },
        )
        assert resp.status_code == 400
    finally:
        settings.grounded_rollout_mode = original


def _user_id(username):
    db = SessionLocal()
    try:
        from bebcare.models.user import User

        return db.query(User).filter(User.username == username).one().user_id
    finally:
        db.close()


def _seed_compare_run(
    *,
    owner_user_id,
    compare_group_id,
    pipeline,
    product_id=None,
    with_artifact=True,
    selected=False,
    cdn_url="https://cdn.test/out.jpg",
):
    from bebcare.services.generation_run_store import add_artifacts, create_generation_run

    db = SessionLocal()
    try:
        run = create_generation_run(
            db,
            owner_user_id=owner_user_id,
            source="studio",
            product_id=product_id,
            generate_task_id=None,
            rollout_mode_at_start="studio",
            experiment_variant="grounded_prompt_role_transport_v1",
            requested_pipeline_version="grounded_refs_v1",
            executed_pipeline_version="grounded_prompt_role_transport_v1",
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline=pipeline,
            compare_group_id=compare_group_id,
            reference_manifest={"version": "ref_manifest_v1", "items": []},
            provider_id=None,
            model=None,
            image_size=None,
            image_provider_mode="byok",
        )
        if with_artifact:
            add_artifacts(db, run, [cdn_url])
            db.flush()
            arts = (
                db.query(GenerationArtifact)
                .filter(GenerationArtifact.run_id == run.run_id)
                .all()
            )
            if selected:
                for art in arts:
                    art.selected = True
        db.commit()
        return run.run_id
    finally:
        db.close()


def test_compare_selection_is_tenant_isolated(full_client, auth_headers):
    headers_v = register_or_create_user(
        full_client, auth_headers, "cmp_v", "cmp_v@test.local", "PassCmpV123!"
    )
    headers_a = register_or_create_user(
        full_client, auth_headers, "cmp_a", "cmp_a@test.local", "PassCmpA123!"
    )
    victim_id = _user_id("cmp_v")
    group_id = "tenant-compare-group"
    _seed_compare_run(
        owner_user_id=victim_id,
        compare_group_id=group_id,
        pipeline="vision_scene",
        selected=False,
    )
    denied = full_client.post(
        "/v1/generate/compare-selection/",
        headers=headers_a,
        json={"compare_group_id": group_id, "image_prompt_pipeline": "vision_scene"},
    )
    assert denied.status_code == 404
    assert denied.json().get("detail") == "Not found"
    db = SessionLocal()
    try:
        run = (
            db.query(GenerationRun)
            .filter(GenerationRun.compare_group_id == group_id)
            .one()
        )
        assert all(not art.selected for art in run.artifacts)
    finally:
        db.close()
    ok = full_client.post(
        "/v1/generate/compare-selection/",
        headers=headers_v,
        json={"compare_group_id": group_id, "image_prompt_pipeline": "vision_scene"},
    )
    assert ok.status_code == 200, ok.text


def test_compare_selection_clears_only_same_group_siblings(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "cmp_sib", "cmp_sib@test.local", "PassCmpSib123!"
    )
    owner_id = _user_id("cmp_sib")
    group_a = "compare-group-a"
    group_b = "compare-group-b"
    _seed_compare_run(
        owner_user_id=owner_id,
        compare_group_id=group_a,
        pipeline="legacy_scene",
        cdn_url="https://cdn.test/a-legacy.jpg",
    )
    _seed_compare_run(
        owner_user_id=owner_id,
        compare_group_id=group_a,
        pipeline="vision_scene",
        cdn_url="https://cdn.test/a-vision.jpg",
    )
    other_id = _seed_compare_run(
        owner_user_id=owner_id,
        compare_group_id=group_b,
        pipeline="vision_scene",
        selected=True,
        cdn_url="https://cdn.test/b-vision.jpg",
    )
    resp = full_client.post(
        "/v1/generate/compare-selection/",
        headers=headers,
        json={"compare_group_id": group_a, "image_prompt_pipeline": "vision_scene"},
    )
    assert resp.status_code == 200, resp.text
    db = SessionLocal()
    try:
        a_runs = (
            db.query(GenerationRun)
            .filter(GenerationRun.compare_group_id == group_a)
            .all()
        )
        selected = {
            run.image_prompt_pipeline
            for run in a_runs
            if any(art.selected for art in run.artifacts)
        }
        assert selected == {"vision_scene"}
        other = db.query(GenerationRun).filter(GenerationRun.run_id == other_id).one()
        assert all(art.selected for art in other.artifacts)
    finally:
        db.close()


def test_compare_selection_missing_artifacts_does_not_404(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "cmp_race", "cmp_race@test.local", "PassCmpRace123!"
    )
    owner_id = _user_id("cmp_race")
    group_id = "compare-missing-artifacts"
    _seed_compare_run(
        owner_user_id=owner_id,
        compare_group_id=group_id,
        pipeline="vision_scene",
        with_artifact=False,
    )
    resp = full_client.post(
        "/v1/generate/compare-selection/",
        headers=headers,
        json={"compare_group_id": group_id, "image_prompt_pipeline": "vision_scene"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 0
