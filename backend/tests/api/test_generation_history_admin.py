"""Admin generation history list/detail API."""

from bebcare.database import SessionLocal
from bebcare.models.generation_quality_finding import GenerationArtifactQualityFinding
from bebcare.models.user import User
from bebcare.services.generation_run_store import (
    add_artifacts,
    create_generation_run,
    finish_generation_run,
)
from conftest import register_or_create_user


def _create_run(
    *,
    owner_user_id: str,
    source: str = "studio",
    status: str = "succeeded",
    product_id: str | None = None,
    output_snapshot: dict | None = None,
) -> str:
    db = SessionLocal()
    try:
        run = create_generation_run(
            db,
            owner_user_id=owner_user_id,
            source=source,
            product_id=product_id,
            generate_task_id=None,
            rollout_mode_at_start="studio",
            experiment_variant=None,
            requested_pipeline_version="baseline_current",
            executed_pipeline_version="grounded_prompt_v1",
            fallback_reason=None,
            fallback_path=None,
            image_prompt_pipeline="vision_scene",
            compare_group_id=None,
            generation_plan=None,
            reference_manifest={
                "version": "ref_manifest_v1",
                "items": [{"order": 0, "role": "primary_subject", "cdn_url": "https://cdn.test/ref.jpg"}],
            },
            provider_id=None,
            model="test-model",
            image_size="1024x1024",
            image_provider_mode="platform",
        )
        finish_generation_run(
            db,
            run,
            status=status,
            image_urls=["https://cdn.test/out.jpg"],
            output_snapshot=output_snapshot
            or {
                "image_prompt": "A lifestyle product photo",
                "copywriting": "Buy now",
                "dimensions": {"scene": "kitchen"},
            },
        )
        db.commit()
        return run.run_id
    finally:
        db.close()


def test_non_admin_cannot_list_generation_history(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "gh_na", "gh_na@test.local", "PassGHNA123!"
    )
    resp = full_client.get("/v1/admin/generation-runs", headers=headers)
    assert resp.status_code == 403


def test_admin_lists_cross_user_runs(full_client, auth_headers):
    user_headers = register_or_create_user(
        full_client, auth_headers, "gh_user", "gh_user@test.local", "PassGHUser123!"
    )
    me = full_client.get("/v1/auth/me", headers=user_headers).json()
    run_id = _create_run(owner_user_id=me["user_id"], source="studio")

    resp = full_client.get("/v1/admin/generation-runs", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    assert any(item["run_id"] == run_id for item in body["items"])
    item = next(row for row in body["items"] if row["run_id"] == run_id)
    assert item["user"]["username"] == "gh_user"
    assert item["thumbnail_url"] == "https://cdn.test/out.jpg"
    assert "diagnosis_line" in item


def test_admin_filters_by_user_id(full_client, auth_headers):
    user_a = register_or_create_user(
        full_client, auth_headers, "gh_filter_a", "gh_filter_a@test.local", "PassGHFA123!"
    )
    user_b = register_or_create_user(
        full_client, auth_headers, "gh_filter_b", "gh_filter_b@test.local", "PassGHFB123!"
    )
    me_a = full_client.get("/v1/auth/me", headers=user_a).json()
    me_b = full_client.get("/v1/auth/me", headers=user_b).json()
    run_a = _create_run(owner_user_id=me_a["user_id"], source="studio")
    _create_run(owner_user_id=me_b["user_id"], source="automation")

    resp = full_client.get(
        f"/v1/admin/generation-runs?user_id={me_a['user_id']}&status=succeeded&source=studio",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    ids = {item["run_id"] for item in resp.json()["items"]}
    assert run_a in ids
    assert all(item["user"]["user_id"] == me_a["user_id"] for item in resp.json()["items"])


def test_admin_get_run_detail(full_client, auth_headers):
    user_headers = register_or_create_user(
        full_client, auth_headers, "gh_detail", "gh_detail@test.local", "PassGHDetail123!"
    )
    me = full_client.get("/v1/auth/me", headers=user_headers).json()
    run_id = _create_run(owner_user_id=me["user_id"])

    db = SessionLocal()
    try:
        finding = GenerationArtifactQualityFinding(
            generation_run_id=run_id,
            stage="post_generation",
            check_code="invented_logo",
            severity="warning",
            passed=False,
            details={"candidate_index": 0},
            policy_version="v1",
        )
        finding.owner_user_id = me["user_id"]
        db.add(finding)
        db.commit()
    finally:
        db.close()

    resp = full_client.get(f"/v1/admin/generation-runs/{run_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["run_id"] == run_id
    assert detail["output_snapshot"]["image_prompt"] == "A lifestyle product photo"
    assert detail["artifacts"][0]["cdn_url"] == "https://cdn.test/out.jpg"
    assert detail["quality_findings"]
    assert detail["quality_findings"][0]["check_label"] == "Invented logo or branding"
    assert detail["qa_summary"]["warning_count"] >= 1


def test_admin_detail_not_found(full_client, auth_headers):
    resp = full_client.get(
        "/v1/admin/generation-runs/00000000-0000-0000-0000-000000000099",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_admin_filter_by_username(full_client, auth_headers):
    user_headers = register_or_create_user(
        full_client, auth_headers, "gh_username_x", "gh_username_x@test.local", "PassGHUN123!"
    )
    me = full_client.get("/v1/auth/me", headers=user_headers).json()
    run_id = _create_run(owner_user_id=me["user_id"])

    resp = full_client.get(
        "/v1/admin/generation-runs?username=gh_username",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert any(item["run_id"] == run_id for item in resp.json()["items"])
