from bebcare.services.logo_policy import (
    LOGO_IN_IMAGES_COMPOSITE,
    LOGO_IN_IMAGES_OMIT,
    LOGO_IN_IMAGES_PRESERVE,
    build_logo_constraint_block,
    resolve_effective_logo_mode,
    should_composite_logo,
)


def test_product_without_branding_forces_omit():
    mode = resolve_effective_logo_mode(
        {"logo_in_images": "preserve", "has_on_body_branding": False}
    )
    assert mode == LOGO_IN_IMAGES_OMIT


def test_preserve_mode_default():
    mode = resolve_effective_logo_mode({})
    assert mode == LOGO_IN_IMAGES_PRESERVE


def test_preserve_constraint_mentions_reference_only():
    block = build_logo_constraint_block(
        {"logo_in_images": "preserve", "logo_font_rule": "solid black wordmark"}
    )
    assert "参考图" in block
    assert "solid black wordmark" in block
    assert "禁止新增" in block


def test_omit_constraint():
    block = build_logo_constraint_block({"logo_in_images": "omit"})
    assert "禁止" in block


def test_composite_should_overlay_when_logo_present():
    assert should_composite_logo(
        {"logo_in_images": "composite", "logo_url": "https://cdn.example/logo.png"}
    )


def test_composite_skipped_without_logo_url():
    assert not should_composite_logo({"logo_in_images": "composite", "logo_url": None})
