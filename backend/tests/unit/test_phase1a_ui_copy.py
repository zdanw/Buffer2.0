from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_compare_credit_copy_present():
    pages = (ROOT / "frontend" / "src" / "i18n" / "locales" / "pages.ts").read_text(
        encoding="utf-8"
    )
    assert "compareUsesTwoCredits" in pages
    assert "2 platform image credits" in pages
    assert "2 次平台出图额度" in pages


def test_preferred_copy_present():
    pages = (ROOT / "frontend" / "src" / "i18n" / "locales" / "pages.ts").read_text(
        encoding="utf-8"
    )
    assert "setPreferred" in pages
    assert "preferred:" in pages


def test_automation_hides_compare_toggle():
    task_page = (
        ROOT / "frontend" / "src" / "pages" / "TaskConfiguration.tsx"
    ).read_text(encoding="utf-8")
    assert "showCompareToggle={false}" in task_page
    controls = (
        ROOT / "frontend" / "src" / "components" / "ImageGenerationControls.tsx"
    ).read_text(encoding="utf-8")
    assert "showCompareToggle = true" in controls
