"""Logo handling policy for image prompt generation and export compositing."""

from __future__ import annotations

from typing import Dict, List

LOGO_IN_IMAGES_PRESERVE = "preserve"
LOGO_IN_IMAGES_OMIT = "omit"
LOGO_IN_IMAGES_COMPOSITE = "composite"

VALID_LOGO_IN_IMAGES = frozenset(
    {LOGO_IN_IMAGES_PRESERVE, LOGO_IN_IMAGES_OMIT, LOGO_IN_IMAGES_COMPOSITE}
)


def resolve_effective_logo_mode(product_info: Dict) -> str:
    """Product-level override wins; otherwise use brand kit logo_in_images."""
    if product_info.get("has_on_body_branding") is False:
        return LOGO_IN_IMAGES_OMIT
    mode = (product_info.get("logo_in_images") or LOGO_IN_IMAGES_PRESERVE).strip().lower()
    if mode not in VALID_LOGO_IN_IMAGES:
        return LOGO_IN_IMAGES_PRESERVE
    return mode


def build_logo_constraint_lines(product_info: Dict) -> List[str]:
    mode = resolve_effective_logo_mode(product_info)
    if mode == LOGO_IN_IMAGES_PRESERVE:
        lines = [
            "仅保留参考图中已有的产品印刷标识；禁止新增、移动、重绘、改色或编造品牌logo；"
            "若参考图中无标识则不要生成任何品牌文字或logo"
        ]
        rule = (product_info.get("logo_font_rule") or "").strip()
        if rule:
            lines.append(f"印刷标识保真要求：{rule}")
        return lines
    if mode == LOGO_IN_IMAGES_OMIT:
        return ["禁止画面中任何品牌文字、logo、水印或产品印刷标识"]
    if mode == LOGO_IN_IMAGES_COMPOSITE:
        return [
            "生成时禁止任何品牌文字、logo或水印；"
            "品牌标识将在导出时由官方素材单独叠加，不要在画面中绘制"
        ]
    return []


def build_logo_constraint_block(product_info: Dict, *, start_index: int = 5) -> str:
    lines = build_logo_constraint_lines(product_info)
    if not lines:
        return ""
    return "\n".join(f"{start_index + i}. {line}" for i, line in enumerate(lines))


def build_vision_logo_instruction(product_info: Dict) -> str:
    lines = build_logo_constraint_lines(product_info)
    if not lines:
        return ""
    return "品牌标识规则：" + "；".join(lines) + "。"


def should_composite_logo(product_info: Dict) -> bool:
    return (
        resolve_effective_logo_mode(product_info) == LOGO_IN_IMAGES_COMPOSITE
        and bool((product_info.get("logo_url") or "").strip())
    )
