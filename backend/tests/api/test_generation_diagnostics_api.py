"""API E2E for compact generation diagnostics. No paid provider calls."""

from bebcare.config.settings import settings


def test_reference_selection_planned_qds_off(full_client, auth_headers):
    original = settings.quality_diversity_selector_mode
    settings.quality_diversity_selector_mode = "off"
    try:
        products = full_client.get("/v1/products/", headers=auth_headers)
        assert products.status_code == 200
        items = products.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("products") or []
        if not items:
            return
        product_id = items[0]["product_id"]
        live = full_client.post(
            "/v1/generate/reference-selection/",
            headers=auth_headers,
            json={"product_id": product_id, "reference_count": 1, "use_scene_reference": False},
        )
        assert live.status_code == 200, live.text
        diag = live.json().get("generation_diagnostics") or {}
        assert diag.get("state") == "planned"
        diversity = next(row for row in diag["summary"] if row["key"] == "diversity")
        assert diversity["status"] == "off"
        assert diversity["message_key"] == "qds_off"
    finally:
        settings.quality_diversity_selector_mode = original


def test_admin_history_legacy_run_no_crash(full_client, auth_headers):
    listed = full_client.get("/v1/admin/generation-runs", headers=auth_headers)
    assert listed.status_code == 200
    denied = full_client.get("/v1/admin/generation-runs")
    assert denied.status_code in (401, 403)
