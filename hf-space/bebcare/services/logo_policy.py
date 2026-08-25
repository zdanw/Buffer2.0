"""Logo handling policy for image prompt generation and export compositing."""

from __future__ import annotations

import re
from typing import Dict, List

LOGO_IN_IMAGES_PRESERVE = "preserve"
LOGO_IN_IMAGES_OMIT = "omit"
LOGO_IN_IMAGES_COMPOSITE = "composite"

VALID_LOGO_IN_IMAGES = frozenset(
    {LOGO_IN_IMAGES_PRESERVE, LOGO_IN_IMAGES_OMIT, LOGO_IN_IMAGES_COMPOSITE}
)

# Rules that tell the model to invent a logo — incompatible with preserve/omit.
_SYNTHESIZE_LOGO_RULE_RE = re.compile(
    r"(always\s+use|use\s+(the\s+)?official|logo\s+asset|without\s+recreat)",
    re.IGNORECASE,
)

# Dimension preset phrases that nudge the prompt LLM to feature/invent a logo.
_DIMENSION_LOGO_PHRASE_RE = re.compile(
    r"[，、及与和\s]*品牌\s*logo|logo\s*细节|品牌\s*标识",
    re.IGNORECASE,
)


def resolve_effective_logo_mode(product_info: Dict) -> str:
    """Product-level override wins; otherwise use brand kit logo_in_images."""
    if product_info.get("has_on_body_branding") is False:
        return LOGO_IN_IMAGES_OMIT
    mode = (product_info.get("logo_in_images") or LOGO_IN_IMAGES_PRESERVE).strip().lower()
    if mode not in VALID_LOGO_IN_IMAGES:
        return LOGO_IN_IMAGES_PRESERVE
    return mode


def sanitize_logo_font_rule(rule: str, mode: str) -> str:
    """Drop legacy rules that ask the model to add/synthesize a logo."""
    text = (rule or "").strip()
    if not text or mode not in (LOGO_IN_IMAGES_PRESERVE, LOGO_IN_IMAGES_OMIT):
        return text
    if _SYNTHESIZE_LOGO_RULE_RE.search(text):
        return ""
    return text


def sanitize_dimension_text(text: str, mode: str) -> str:
    """Remove logo-focus phrases from dimension labels when not compositing."""
    label = (text or "").strip()
    if not label or mode == LOGO_IN_IMAGES_COMPOSITE:
        return label
    cleaned = _DIMENSION_LOGO_PHRASE_RE.sub("", label)
    cleaned = re.sub(r"[，、]{2,}", "，", cleaned)
    cleaned = re.sub(r"[，、]\s*$", "", cleaned)
    return cleaned.strip()


def build_logo_constraint_lines(product_info: Dict) -> List[str]:
    mode = resolve_effective_logo_mode(product_info)
    if mode == LOGO_IN_IMAGES_PRESERVE:
        lines = [
            "仅保留参考图中已有的产品印刷标识；禁止新增、移动、重绘、改色或编造品牌logo；"
            "若参考图中无标识则不要生成任何品牌文字或logo；"
            "禁止描述参考图中不存在的logo位置、字样或颜色"
        ]
        rule = sanitize_logo_font_rule(
            (product_info.get("logo_font_rule") or "").strip(), mode
        )
        if rule:
            lines.append(f"印刷标识保真要求（仅当参考图可见时）：{rule}")
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
