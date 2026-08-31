"""Visual setup UX: catalog context for Phase 2B and Product form copy."""

from pathlib import Path
from unittest.mock import patch

from bebcare.config.settings import settings
from bebcare.schemas.asset_intelligence import (
    compact_catalog_context,
    offering_context_version,
)
from bebcare.services.asset_intelligence import enqueue_selected_intelligence
from bebcare.services.asset_intelligence_adapter import analyze_reference_image
from conftest import register_or_create_user

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "frontend" / "src" / "pages" / "AssetManagement.tsx"
COMBO = ROOT / "frontend" / "src" / "components" / "CategoryCombobox.tsx"
VISUAL = ROOT / "frontend" / "src" / "components" / "VisualSetupRow.tsx"
SETUP = ROOT / "frontend" / "src" / "lib" / "visualSetup.ts"
PAGES = ROOT / "frontend" / "src" / "i18n" / "locales" / "pages.ts"


def test_category_remains_required_creatable_combobox():
    assets = ASSETS.read_text(encoding="utf-8")
    combo = COMBO.read_text(encoding="utf-8")
    snippet = assets[assets.index("<CategoryCombobox") : assets.index("<CategoryCombobox") + 280]
    assert "required" in snippet
    assert "getCategories" in combo
    assert "createNew" in combo or "Create" in combo
    assert "OFFERING_TYPES" not in assets


def test_form_hides_offering_type_and_unknown():
    assets = ASSETS.read_text(encoding="utf-8")
    visual = VISUAL.read_text(encoding="utf-8")
    pages = PAGES.read_text(encoding="utf-8")
    assert "assets.offeringType" not in assets
    assert "Automatic / Unknown" not in assets
    assert "Automatic / Unknown" not in visual
    assert "Automatic / Unknown" not in pages
    assert "Offering type" not in assets
    assert "visualSetupAutoDetect" in visual
    assert "VISUAL_SETUP_MENU" in visual
    assert assets.index("CategoryCombobox") < assets.index("VisualSetupRow")
    assert "=== 'unknown'" in assets
    assert "offering_type_suggestion" in assets
    assert "suggestion=" in assets


def test_visual_setup_row_states_and_menu():
    visual = VISUAL.read_text(encoding="utf-8")
    pages = PAGES.read_text(encoding="utf-8")
    assert "Visual setup (optional)" in pages
    assert "视觉呈现方式（可选）" in pages
    assert "Auto-detect" in pages
    assert "自动识别" in pages
    assert "Select a type to improve image accuracy." in pages
    assert "选择类型可提高图片准确度。" in pages
    assert "visualSetupSuggested" in visual
    assert "visualSetupChoose" not in visual
    assert "visualSetupChange" in visual
    assert "VISUAL_SETUP_MENU" in visual
    assert "w-full" in visual
    assert "onClick={() => setOpen((v) => !v)}" in visual
    assert "Escape" in visual
    assert "mousedown" in visual
    assert "ArrowDown" in visual
    assert "role=\"listbox\"" in visual
    assert "aria-selected" in visual
    assert "Check" in visual
    assert "hover:bg-forge-50" in visual
    assert "focus:bg-forge-50" in visual
    assert "setOpen(false)" in visual
    assert "suggested && !explicit" in visual or "!explicit ? visualSetupChoiceKey(suggestion)" in visual
    assert "persistVisualSetupChoice(current, choice)" in visual
    assert "py-1.5" in visual
    assert "absolute left-0 right-0 z-30 mt-1" in visual
    assert "Automatic / Unknown" not in pages


def test_six_friendly_choices_and_software_saas_mapping():
    setup = SETUP.read_text(encoding="utf-8")
    assert all(
        key in setup
        for key in (
            "physical_product",
            "software",
            "service",
            "digital_product",
            "event_or_experience",
            "mixed",
        )
    )
    assert "persistVisualSetupChoice" in setup
    assert "current === 'saas'" in setup
    assert "VISUAL_SETUP_MENU" in setup
    assert "['unknown', ...VISUAL_SETUP_CHOICES]" in setup
    assert "if (picked === 'unknown')" in setup
    assert "return 'unknown'" in setup
    pages = PAGES.read_text(encoding="utf-8")
    assert "Software or app" in pages
    assert "软件或应用" in pages
    assert "视觉呈现方式（可选）" in pages
    assert "Select a type to improve image accuracy." in pages


def test_catalog_context_capped_and_in_cache_identity():
    long_desc = "x" * 900
    text = compact_catalog_context("Baby monitors", long_desc, ["a" * 200, "b", "c", "d", "e", "f"])
    assert "Baby monitors" in text
    assert "x" * 400 in text
    assert "x" * 401 not in text
    v1 = offering_context_version("unknown", category="Baby monitors", description="one")
    v2 = offering_context_version("unknown", category="Night lights", description="one")
    v3 = offering_context_version("physical_product", category="Baby monitors", description="one")
    assert v1 != v2
    assert v1 != v3
    assert v1.startswith("offering_v1:unknown:")
    same = offering_context_version("unknown", category="Baby monitors", description="one")
    assert v1 == same


def test_analysis_prompt_includes_catalog_not_full_dump():
    captured = []

    def complete_ok(messages):
        captured.append(messages)
        from tests.unit.test_phase2b_asset_intelligence import _complete_ok

        return _complete_ok()(messages)

    analyze_reference_image(
        image_url="https://cdn.test/x.png",
        offering_type="unknown",
        catalog_context=compact_catalog_context("monitors", "portable night light", ["USB-C"]),
        complete=complete_ok,
    )
    blob = str(captured[0])
    assert "monitors" in blob
    assert "portable night light" in blob
    assert "USB-C" in blob
    assert "Catalog notes" in blob


def test_rollout_off_no_semantic_enqueue():
    original = settings.asset_intelligence_mode
    settings.asset_intelligence_mode = "off"
    try:
        assert (
            enqueue_selected_intelligence(
                image_ids=["x"], owner_user_id="u", product_id="p", source="studio"
            )
            == []
        )
    finally:
        settings.asset_intelligence_mode = original


def test_save_unknown_does_not_write_suggestion(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "vs_unk", "vs_unk@test.local", "PassVsUnk123!"
    )
    brand = full_client.post("/v1/brands/", headers=headers, json={"name": "VS Brand"})
    created = full_client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": "VS SKU",
            "category": "monitors",
            "brand_id": brand.json()["brand_id"],
        },
    )
    assert created.status_code in (200, 201)
    assert created.json()["offering_type"] == "unknown"
    pid = created.json()["product_id"]
    updated = full_client.put(
        f"/v1/products/{pid}",
        headers=headers,
        json={"offering_type": "unknown", "category": "monitors"},
    )
    assert updated.status_code == 200
    assert updated.json()["offering_type"] == "unknown"


def test_manual_software_persists_software_saas_preserved(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "vs_sw", "vs_sw@test.local", "PassVsSw123!"
    )
    brand = full_client.post("/v1/brands/", headers=headers, json={"name": "SW Brand"})
    created = full_client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": "App SKU",
            "category": "apps",
            "brand_id": brand.json()["brand_id"],
            "offering_type": "saas",
        },
    )
    assert created.json()["offering_type"] == "saas"
    keep = full_client.put(
        f"/v1/products/{created.json()['product_id']}",
        headers=headers,
        json={"offering_type": "saas"},
    )
    assert keep.json()["offering_type"] == "saas"
    switched = full_client.put(
        f"/v1/products/{created.json()['product_id']}",
        headers=headers,
        json={"offering_type": "software"},
    )
    assert switched.json()["offering_type"] == "software"


def test_form_does_not_call_analyze_on_open():
    assets = ASSETS.read_text(encoding="utf-8")
    visual = VISUAL.read_text(encoding="utf-8")
    assert "analyze_reference_image" not in assets
    assert "enqueue_selected_intelligence" not in assets
    assert "run_intelligence_job" not in assets + visual
    assert "analyzeReference" not in assets + visual
    assert "complete(" not in visual


def test_suggestion_only_when_offering_unknown_in_form():
    assets = ASSETS.read_text(encoding="utf-8")
    visual = VISUAL.read_text(encoding="utf-8")
    assert "(formData.offering_type || 'unknown') === 'unknown'" in assets
    assert "selectedProduct?.offering_type_suggestion" in assets
    assert "!explicit ? visualSetupChoiceKey(suggestion)" in visual
    assert "persistVisualSetupChoice" in visual


def test_unknown_get_has_no_suggestion(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "vs_get", "vs_get@test.local", "PassVsGet123!"
    )
    brand = full_client.post("/v1/brands/", headers=headers, json={"name": "VS Get Brand"})
    created = full_client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": "VS Get SKU",
            "category": "monitors",
            "brand_id": brand.json()["brand_id"],
        },
    )
    assert created.status_code in (200, 201)
    assert created.json()["offering_type"] == "unknown"
    assert created.json().get("offering_type_suggestion") in (None, "unknown")
    fetched = full_client.get(f"/v1/products/{created.json()['product_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["offering_type"] == "unknown"
    assert fetched.json().get("offering_type_suggestion") in (None, "unknown")


def test_cached_suggestion_does_not_override_or_auto_persist(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "vs_sug", "vs_sug@test.local", "PassVsSug123!"
    )
    brand = full_client.post("/v1/brands/", headers=headers, json={"name": "VS Sug Brand"})
    created = full_client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": "VS Sug SKU",
            "category": "monitors",
            "brand_id": brand.json()["brand_id"],
        },
    )
    pid = created.json()["product_id"]
    packed = {
        "by_image": {},
        "offering_type_suggestion": "physical_product",
    }
    with patch(
        "bebcare.services.asset_intelligence.compact_labels_for_product",
        return_value=packed,
    ):
        fetched = full_client.get(f"/v1/products/{pid}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["offering_type"] == "unknown"
        assert fetched.json()["offering_type_suggestion"] == "physical_product"

        kept = full_client.put(
            f"/v1/products/{pid}",
            headers=headers,
            json={"offering_type": "unknown", "category": "monitors"},
        )
        assert kept.status_code == 200
        assert kept.json()["offering_type"] == "unknown"

        explicit = full_client.put(
            f"/v1/products/{pid}",
            headers=headers,
            json={"offering_type": "physical_product", "category": "monitors"},
        )
        assert explicit.status_code == 200
        assert explicit.json()["offering_type"] == "physical_product"

        still = full_client.get(f"/v1/products/{pid}", headers=headers)
        assert still.json()["offering_type"] == "physical_product"
        assert still.json()["offering_type_suggestion"] == "physical_product"


def test_explicit_selection_wins_over_cached_suggestion(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "vs_exp", "vs_exp@test.local", "PassVsExp123!"
    )
    brand = full_client.post("/v1/brands/", headers=headers, json={"name": "VS Exp Brand"})
    created = full_client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": "VS Exp SKU",
            "category": "apps",
            "brand_id": brand.json()["brand_id"],
            "offering_type": "service",
        },
    )
    pid = created.json()["product_id"]
    packed = {
        "by_image": {},
        "offering_type_suggestion": "physical_product",
    }
    with patch(
        "bebcare.services.asset_intelligence.compact_labels_for_product",
        return_value=packed,
    ):
        fetched = full_client.get(f"/v1/products/{pid}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["offering_type"] == "service"
        assert fetched.json()["offering_type_suggestion"] == "physical_product"
        assets = ASSETS.read_text(encoding="utf-8")
        assert "=== 'unknown'" in assets
        assert "offering_type_suggestion" in assets


def test_revert_to_auto_detect_writes_unknown_and_allows_suggestion(full_client, auth_headers):
    headers = register_or_create_user(
        full_client, auth_headers, "vs_rev", "vs_rev@test.local", "PassVsRev123!"
    )
    brand = full_client.post("/v1/brands/", headers=headers, json={"name": "VS Rev Brand"})
    created = full_client.post(
        "/v1/products/",
        headers=headers,
        json={
            "product_name": "VS Rev SKU",
            "category": "apps",
            "brand_id": brand.json()["brand_id"],
            "offering_type": "saas",
        },
    )
    pid = created.json()["product_id"]
    assert created.json()["offering_type"] == "saas"
    reverted = full_client.put(
        f"/v1/products/{pid}",
        headers=headers,
        json={"offering_type": "unknown", "category": "apps"},
    )
    assert reverted.status_code == 200
    assert reverted.json()["offering_type"] == "unknown"
    packed = {
        "by_image": {},
        "offering_type_suggestion": "software",
    }
    with patch(
        "bebcare.services.asset_intelligence.compact_labels_for_product",
        return_value=packed,
    ):
        fetched = full_client.get(f"/v1/products/{pid}", headers=headers)
        assert fetched.json()["offering_type"] == "unknown"
        assert fetched.json()["offering_type_suggestion"] == "software"
    setup = SETUP.read_text(encoding="utf-8")
    assert "picked === 'unknown'" in setup
    visual = VISUAL.read_text(encoding="utf-8")
    assert "item === 'unknown'" in visual

