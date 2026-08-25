"""Locale-aware prompt text for copywriting and image generation."""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

DEFAULT_DIM_LABELS_EN = {
    "默认场景": "Default scene",
    "默认光线": "Default lighting",
    "默认风格": "Default style",
    "默认细节": "Default details",
    "默认视角": "Default viewpoint",
    "默认构图": "Default composition",
    "默认画质": "Default quality",
}

SCENE_REF_LABELS = {
    "zh": {
        "scene": "参考场景图",
        "follow_ref": "沿用参考图",
        "vision_scene": "参考场景图+视觉模型",
        "vision_auto": "视觉模型自主",
        "vision_scene_fusion": "视觉模型自主(场景融合)",
    },
    "en": {
        "scene": "Scene reference",
        "follow_ref": "Match reference",
        "vision_scene": "Scene reference + vision model",
        "vision_auto": "Vision model auto",
        "vision_scene_fusion": "Vision model (scene fusion)",
    },
}

NEGATIVE_PROMPT = {
    "zh": {
        "hard_rules": [
            "水印", "文字", "二维码", "网址", "网站",
            "商标", "标志", "品牌名称", "标签", "边框",
            "徽章", "平台标志", "产品形状改变",
            "无关产品", "颜色篡改", "缺失部件",
            "模糊", "扭曲", "低质量", "丑陋",
        ],
        "soft_suggestions": [
            "避免重复构图",
            "避免相似背景",
            "避免匹配色调",
            "避免杂乱",
        ],
    },
    "en": {
        "hard_rules": [
            "watermark", "text", "QR code", "URL", "website",
            "trademark", "logo", "brand name", "label", "border",
            "badge", "platform logo", "altered product shape",
            "unrelated products", "color shift", "missing parts",
            "blur", "distortion", "low quality", "ugly",
        ],
        "soft_suggestions": [
            "avoid repeated composition",
            "avoid similar background",
            "avoid matching color palette",
            "avoid clutter",
        ],
    },
}

NARRATIVE_PERSPECTIVES = {
    "zh": [
        {"id": "tech_reviewer", "name": "科技测评师", "description": "专业、技术型测评风格"},
        {"id": "busy_mom", "name": "忙碌妈妈", "description": "真实、贴近生活的妈妈视角"},
        {"id": "humorist", "name": "幽默达人", "description": "轻松、有趣的表达方式"},
        {"id": "tech_blogger", "name": "科技博主", "description": "前沿、专业的科技分析"},
        {"id": "lifestyle", "name": "生活美学爱好者", "description": "优雅、精致的生活方式"},
        {"id": "new_parent", "name": "新手父母", "description": "真诚、朴实的育儿体验"},
    ],
    "en": [
        {"id": "tech_reviewer", "name": "Tech reviewer", "description": "Professional, technical review tone"},
        {"id": "busy_mom", "name": "Busy parent", "description": "Authentic, relatable everyday perspective"},
        {"id": "humorist", "name": "Humorist", "description": "Light, playful expression"},
        {"id": "tech_blogger", "name": "Tech blogger", "description": "Forward-looking, expert analysis"},
        {"id": "lifestyle", "name": "Lifestyle enthusiast", "description": "Elegant, refined lifestyle tone"},
        {"id": "new_parent", "name": "New parent", "description": "Honest, heartfelt parenting experience"},
    ],
}

WRITING_STYLES = {
    "zh": [
        {"id": "种草风", "name": "种草风格", "description": "友好、推荐式文案"},
        {"id": "理性分析", "name": "理性分析", "description": "深入、逻辑分析"},
        {"id": "温情故事", "name": "温情故事", "description": "暖心、叙事风格"},
        {"id": "硬核测评", "name": "硬核测评", "description": "专业、客观测评"},
        {"id": "幽默搞笑", "name": "幽默搞笑", "description": "轻松、有趣风格"},
        {"id": "情感共鸣", "name": "情感共鸣", "description": "感人、情感文案"},
    ],
    "en": [
        {"id": "recommendation", "name": "Recommendation style", "description": "Friendly, suggestive copy"},
        {"id": "analytical", "name": "Analytical", "description": "In-depth, logical analysis"},
        {"id": "storytelling", "name": "Heartwarming story", "description": "Warm, narrative style"},
        {"id": "hardcore_review", "name": "Hardcore review", "description": "Professional, objective review"},
        {"id": "humor", "name": "Humorous", "description": "Light, fun tone"},
        {"id": "emotional", "name": "Emotional resonance", "description": "Moving, emotional copy"},
    ],
}


def normalize_locale(locale: Optional[str]) -> str:
    if not locale:
        return "zh"
    value = str(locale).lower().strip().replace("_", "-")
    if value.startswith("en"):
        return "en"
    return "zh"


def locale_from_product_info(product_info: Optional[Dict]) -> str:
    if not product_info:
        return "zh"
    return normalize_locale(product_info.get("locale"))


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def dimension_display_name(
    item: Dict,
    locale: str,
    *,
    sanitizer: Optional[Callable[[str], str]] = None,
) -> str:
    """Pick a display label for dimension cards; English falls back to item id."""
    loc = normalize_locale(locale)
    name = (item.get("name") or "").strip()
    if loc == "en":
        if item.get("name_en"):
            raw = str(item["name_en"]).strip()
        elif name in DEFAULT_DIM_LABELS_EN:
            raw = DEFAULT_DIM_LABELS_EN[name]
        elif _has_cjk(name):
            item_id = (item.get("id") or "").strip()
            raw = (
                item_id.replace("_", " ").replace("-", " ").title()
                if item_id and item_id != "default"
                else name
            )
        else:
            raw = name or "Default"
    else:
        raw = name or "默认"
    if sanitizer:
        return sanitizer(raw)
    return raw


def build_negative_prompt(locale: str) -> str:
    loc = normalize_locale(locale)
    data = NEGATIVE_PROMPT[loc]
    hard_rules = ", ".join(data["hard_rules"])
    soft_rules = ", ".join(data["soft_suggestions"])
    return f"{hard_rules}, {soft_rules}"


def default_copy_system_prompt(locale: str) -> str:
    if normalize_locale(locale) == "en":
        return """
You are a professional social media marketing expert.
You create high-quality English social posts and image prompts.

Follow these principles:
1. Match the brand voice when provided; otherwise stay neutral and factual
2. Highlight core product benefits
3. Use emojis appropriately for the platform
4. Match the target platform tone and length
5. Image prompts must describe scene, lighting, and composition clearly
6. Social posts must be in English
7. Post length 120-200 characters including hashtags when applicable
""".strip()
    return """
你是一位专业的社交媒体营销专家，擅长撰写高质量的中文社媒帖子和图像提示词。

遵循以下原则：
1. 有品牌调性时保持一致；否则保持中性、客观
2. 突出产品核心卖点
3. 根据平台适当使用表情符号
4. 匹配目标平台的语气与篇幅
5. 图像提示词需清晰描述场景、光线与构图
6. 社媒帖子必须使用中文
7. 帖子长度 120-200 字（含话题标签）
""".strip()


def image_prompt_system_prompt(locale: str) -> str:
    if normalize_locale(locale) == "en":
        return """
You are a professional AI image prompt engineer.
Convert product information and dimension options into a detailed, vivid English image description for downstream image models.

Guidelines:
1. Output only the image prompt — no extra text or explanation
2. Use rich, sensory language with concrete adjectives
3. Blend scene, lighting, composition, style, quality, and props into one coherent narrative
4. Describe light direction, quality, color temperature, and how light shapes the product
5. Emphasize material textures and contrasts
6. Match the emotional tone to the product positioning
7. Use lifestyle storytelling: show the product in a believable real-world moment
8. Suitable for commercial product photography with artistic appeal
9. Layer from foreground to background, subject to detail
10. Use precise color descriptions, not vague color words
""".strip()
    return """
你是一位专业的AI图像提示词工程师。
你的任务是将产品信息和维度选项转换为详细、生动、富有感染力的中文图像描述，让AI图像生成器能够完美理解并生成高质量图片。

遵循以下指南：
1. 仅输出图像提示词，不要额外文本或解释
2. 使用丰富细腻的描述性语言，包含大量感官细节和具体形容词
3. 将场景、光线、构图、风格、画质、细节道具等元素自然融合，形成连贯的叙事
4. 注重光影层次：描述光线的方向、质感、色温，以及光影如何塑造产品形态和氛围
5. 强调材质表现：描述产品的材质质感，以及材质之间的对比
6. 营造符合产品定位的情感氛围
7. 采用生活方式叙事：描述产品在真实生活场景中的使用状态
8. 确保适合商业产品摄影，同时具备艺术感染力
9. 描述要有层次感：从前景到背景，从主体到细节，逐步展开
10. 使用精确的色彩描述，避免笼统的颜色词
""".strip()


def vision_image_prompt_system_prompt(locale: str) -> str:
    if normalize_locale(locale) == "en":
        return """
You are a professional AI image prompt engineer focused on commercial product photography.
Write one final English image prompt from the reference images for downstream image generation.

Guidelines:
1. Output only one final English image prompt — no headings, lists, or extra explanation
2. Observe product shape, color, material, proportions, parts, and printed markings in the references
3. Product appearance must match the references — no recoloring, deformation, missing or invented parts
4. If references are studio/white/transparent backgrounds, use them only to lock the product; do not copy the reference background, surface, props, count, or layout
5. Design a fresh lifestyle environment from the given scene dimensions; scene, light, and mood must not copy the reference background
6. Default to one hero product unless dimensions or description require a multi-piece display
7. Use rich sensory language for light, material, and mood
8. No text, watermarks, QR codes, URLs, captions, or extra brand names (except product printing already on the item)
9. Premium commercial lifestyle product photography — clean and immersive
""".strip()
    return """
你是一位专业的AI图像提示词工程师，专注于商业产品摄影。
你将仅根据用户提供的参考图，自主撰写一段最终中文图像提示词，供下游图像生成模型使用。

遵循以下指南：
1. 仅输出一段最终中文图像提示词，不要额外说明、标题或列表前缀
2. 先仔细观察参考图中的产品外形、颜色、材质、比例、部件与印刷标识
3. 产品外观（外形、颜色、材质、比例、部件）必须以参考图为准，禁止改色、变形、缺失或编造部件
4. 参考图若为棚拍/白底/透明底，仅用于锁定产品本身；禁止复制参考图的背景、台面、道具、产品数量与摆放布局
5. 必须根据用户给出的场景维度设计全新的生活方式环境；场景、光线、氛围与参考图背景无关
6. 默认画面中仅展示一个产品主体（英雄单品），除非维度或产品描述明确要求多件套展示
7. 使用丰富细腻的描述性语言，包含光影、材质与情感氛围
8. 画面中禁止生成文字、水印、二维码、网址、字幕或额外品牌名（产品自带印刷除外）
9. 适合高端商业生活方式产品摄影，画面干净、有代入感
""".strip()


def vision_scene_image_prompt_system_prompt(locale: str) -> str:
    if normalize_locale(locale) == "en":
        return """
You are a professional AI image prompt engineer for commercial product scene fusion.
The user provides separate scene and product reference images. Write one final English image prompt for downstream image-to-image fusion.

Guidelines:
1. Output only one final English image prompt — no headings, lists, or extra explanation
2. Product shape, color, material, proportions, angle, and printing must match the product reference
3. Preserve scene composition, spatial layout, overall tone, and light direction; mild atmosphere tweaks only
4. Describe where and how the product sits in the scene, scale, and fusion; replace other products in the scene with this product
5. Props must not block or alter the product; no text, watermarks, QR codes, URLs, or extra brand names
6. Commercial lifestyle photography — clean and immersive
""".strip()
    return """
你是一位专业的AI图像提示词工程师，专注于商业产品「场景融合」摄影。
用户会分别提供场景参考图与产品参考图。你仅根据这些图片，自主撰写一段最终中文图像提示词，供下游图生图模型把产品融入场景。

遵循以下指南：
1. 仅输出一段最终中文图像提示词，不要额外说明、标题或列表前缀
2. 产品外形、颜色、材质、比例、角度与印刷标识必须以产品参考图为准，禁止改色、变形或编造部件
3. 场景构图、空间布局、整体色调与光线方向应尽量沿用场景参考图，可做轻度氛围优化
4. 明确描述：将产品自然放入场景中的位置关系、尺度与融合方式；若场景中有其他产品，用本次产品替换
5. 道具不得遮挡或改变产品主体；禁止文字、水印、二维码、网址或额外品牌名
6. 适合商业生活方式摄影，画面干净、有代入感
""".strip()


def format_recent_prompt_avoidance(recent_prompts: List[str], locale: str) -> str:
    lines = [p.strip() for p in (recent_prompts or []) if p and str(p).strip()]
    if not lines:
        return ""
    numbered = "\n".join(f"{i}. {p}" for i, p in enumerate(lines, 1))
    if normalize_locale(locale) == "en":
        return (
            "\n\nRecent image prompts already used for this product. "
            "This run must differ clearly in scene space, light direction/temperature, "
            "composition/framing, and main props; do not reuse the same space or lighting pattern. "
            "Product appearance must still match the reference images — no recoloring or deformation.\n"
            f"{numbered}"
        )
    return (
        "\n\n以下是该产品最近已使用的图像提示词。本次必须在场景空间、光线方向/色温、"
        "构图景别、主要道具上明显不同；禁止复用相同空间或光影套路。"
        "产品外观仍以参考图为准，禁止改色、变形。\n"
        f"{numbered}"
    )


def format_vision_dimension_hints(
    dimensions: Optional[Dict[str, str]],
    locale: str,
) -> str:
    if not dimensions:
        return ""
    loc = normalize_locale(locale)
    if loc == "en":
        parts = [
            f"Scene: {dimensions.get('scene') or ''}",
            f"Lighting: {dimensions.get('lighting') or ''}",
            f"Composition: {dimensions.get('composition') or ''}",
            f"Viewpoint: {dimensions.get('viewpoint') or ''}",
            f"Style: {dimensions.get('style') or ''}",
            f"Quality: {dimensions.get('quality') or ''}",
            f"Details/props: {dimensions.get('details') or ''}",
        ]
        prefix = (
            "Scene creative dimensions (required; do not copy the reference background): "
        )
    else:
        parts = [
            f"场景：{dimensions.get('scene') or ''}",
            f"光线：{dimensions.get('lighting') or ''}",
            f"构图：{dimensions.get('composition') or ''}",
            f"视角：{dimensions.get('viewpoint') or ''}",
            f"风格：{dimensions.get('style') or ''}",
            f"画质：{dimensions.get('quality') or ''}",
            f"细节/道具：{dimensions.get('details') or ''}",
        ]
        prefix = "场景创意维度（必须采用，不得照搬参考图背景）："
    return prefix + "；".join(parts) + "。"


def scene_ref_labels(locale: str) -> Dict[str, str]:
    return SCENE_REF_LABELS[normalize_locale(locale)]


def narrative_perspectives(locale: str) -> List[Dict]:
    return NARRATIVE_PERSPECTIVES[normalize_locale(locale)]


def writing_styles(locale: str) -> List[Dict]:
    return WRITING_STYLES[normalize_locale(locale)]


def localized_logo_constraint_block(
    product_info: Dict,
    locale: str,
    *,
    start_index: int = 5,
) -> str:
    from bebcare.services.logo_policy import (
        LOGO_IN_IMAGES_COMPOSITE,
        LOGO_IN_IMAGES_OMIT,
        LOGO_IN_IMAGES_PRESERVE,
        resolve_effective_logo_mode,
        sanitize_logo_font_rule,
    )

    mode = resolve_effective_logo_mode(product_info)
    loc = normalize_locale(locale)
    if loc == "en":
        if mode == LOGO_IN_IMAGES_PRESERVE:
            lines = [
                "Keep only printed markings already visible on the product in the reference; "
                "do not add, move, redraw, recolor, or invent a brand logo; "
                "if no marking appears on the reference, generate none",
                "Do not describe logo placement, wording, or colors absent from the reference",
            ]
            rule = sanitize_logo_font_rule(
                (product_info.get("logo_font_rule") or "").strip(), mode
            )
            if rule:
                lines.append(
                    f"Printed marking fidelity (only when visible on reference): {rule}"
                )
        elif mode == LOGO_IN_IMAGES_OMIT:
            lines = [
                "No brand text, logo, watermark, or printed markings anywhere in the image"
            ]
        elif mode == LOGO_IN_IMAGES_COMPOSITE:
            lines = [
                "Do not render any brand text, logo, or watermark; "
                "brand assets will be composited separately at export"
            ]
        else:
            lines = []
    else:
        from bebcare.services.logo_policy import build_logo_constraint_lines

        lines = build_logo_constraint_lines(product_info)

    if not lines:
        return ""
    return "\n".join(f"{start_index + i}. {line}" for i, line in enumerate(lines))


def localized_physics_placement_block(
    product_info: Optional[Dict],
    locale: str,
) -> str:
    from bebcare.prompt_builder.placement_rules import build_physics_placement_block

    if normalize_locale(locale) == "zh":
        return build_physics_placement_block(product_info)

    from bebcare.prompt_builder.placement_rules import resolve_pose_rule

    info = product_info or {}
    category = (info.get("category") or info.get("product_type") or "").strip()
    rule = resolve_pose_rule(category)
    pose_en = {
        "台面直立，支架底部接触桌面": "Upright on a surface, base touching the desk",
        "台面或床头柜直立，底部完全接触": "Upright on a surface or nightstand, base fully touching",
        "台面直立，底部接触": "Upright on a surface, base touching",
        "地面或台面直立，底部接触，垂直于地面": "Upright on floor or surface, base touching, vertical",
        "平放在台面或托盘中，底部完全接触承托面": "Flat on a surface or tray, base fully supported",
        "底部接触承托面，姿态稳定自然": "Base on supporting surface, stable natural pose",
    }.get(rule.get("default") or "", "Base on supporting surface, stable natural pose")
    lines = [
        "Product base must sit on the supporting surface with contact shadow; "
        "perspective must match the scene — no floating or sticker look.",
        f"Placement: {pose_en}.",
    ]
    if rule.get("reflect"):
        lines.append("Bright surfaces may show subtle environmental reflection.")
    return "\n".join(lines)


def localized_vision_logo_instruction(product_info: Dict, locale: str) -> str:
    block = localized_logo_constraint_block(product_info, locale, start_index=1)
    if not block:
        return ""
    lines = [line.split(". ", 1)[-1] if ". " in line else line for line in block.split("\n")]
    if normalize_locale(locale) == "en":
        return "Brand marking rules: " + "; ".join(lines) + "."
    return "品牌标识规则：" + "；".join(lines) + "。"
