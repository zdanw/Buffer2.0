import logging

logger = logging.getLogger(__name__)

from typing import List, Dict, Optional
import json
import random

from bebcare.prompt_builder.dimensions_data import DIMENSIONS

try:
    from bebcare.services.dimension_service import dimension_service
except ImportError:
    dimension_service = None

NEGATIVE_PROMPT = {
    "hard_rules": [
        "水印", "文字", "二维码", "网址", "网站",
        "商标", "标志", "品牌名称", "标签", "边框",
        "徽章", "平台标志", "产品形状改变",
        "无关产品", "颜色篡改", "缺失部件",
        "模糊", "扭曲", "低质量", "丑陋"
    ],
    "soft_suggestions": [
        "避免重复构图",
        "避免相似背景",
        "避免匹配色调",
        "避免杂乱"
    ]
}

PLATFORM_STYLES = {
    "instagram": {
        "tone": "优雅、精致、感性",
        "length": "中等",
        "emoji_ratio": 0.3
    },
    "tiktok": {
        "tone": "活泼、充满活力、有节奏感",
        "length": "简短",
        "emoji_ratio": 0.5
    },
    "facebook": {
        "tone": "详细、温暖、值得信赖",
        "length": "较长",
        "emoji_ratio": 0.1
    }
}

NARRATIVE_PERSPECTIVES = [
    {"id": "tech_reviewer", "name": "科技测评师", "description": "专业、技术型测评风格"},
    {"id": "busy_mom", "name": "忙碌妈妈", "description": "真实、贴近生活的妈妈视角"},
    {"id": "humorist", "name": "幽默达人", "description": "轻松、有趣的表达方式"},
    {"id": "tech_blogger", "name": "科技博主", "description": "前沿、专业的科技分析"},
    {"id": "lifestyle", "name": "生活美学爱好者", "description": "优雅、精致的生活方式"},
    {"id": "new_parent", "name": "新手父母", "description": "真诚、朴实的育儿体验"}
]

WRITING_STYLES = [
    {"id": "种草风", "name": "种草风格", "description": "友好、推荐式文案"},
    {"id": "理性分析", "name": "理性分析", "description": "深入、逻辑分析"},
    {"id": "温情故事", "name": "温情故事", "description": "暖心、叙事风格"},
    {"id": "硬核测评", "name": "硬核测评", "description": "专业、客观测评"},
    {"id": "幽默搞笑", "name": "幽默搞笑", "description": "轻松、有趣风格"},
    {"id": "情感共鸣", "name": "情感共鸣", "description": "感人、情感文案"}
]


class PromptEngine:
    def __init__(self):
        self.system_prompt = """
你是Bebcare高端婴儿品牌的专业营销专家。
你擅长创建高质量的英文社交媒体文案和图像提示词。

遵循以下原则：
1. 保持专业而温暖的语调，适合婴儿产品
2. 突出产品核心卖点
3. 使用适当的表情符号增强情感表达
4. 确保内容符合目标平台特点
5. 图像提示词必须包含详细的场景、光线和构图描述
6. 社交媒体帖子输出仅限英文
7. 帖子长度必须为120-200字（包含所有文本和话题标签）
"""

    _EMPTY_DIMENSIONS = {
        "scenes": [],
        "lighting": [],
        "styles": [],
        "details": [],
        "viewpoints": [],
        "compositions": [],
        "quality": [],
    }

    def _get_dimensions(self, product_type: str = "Night Lights", db=None) -> dict:
        """获取指定产品类型的维度配置。

        新类目在 DB 无维度时不得跨类目回退到 Night Lights，否则会污染提示词。
        无数据时返回空池，由 _select_* 使用「默认*」占位。
        """
        if db is not None and dimension_service is not None:
            try:
                result = dimension_service.get_dimensions_by_product_type(product_type, db)
                if any(result.get(key) for key in self._EMPTY_DIMENSIONS):
                    return result
                logger.info(
                    "No enabled dimensions in DB for product_type '%s'",
                    product_type,
                )
            except Exception as e:
                logger.exception(
                    "dimension_service.get_dimensions_by_product_type failed: %s", e
                )

        if product_type in DIMENSIONS:
            return DIMENSIONS[product_type]

        logger.warning(
            "No dimensions for product_type '%s' (DB empty / not in static seed); "
            "using empty pools instead of Night Lights fallback",
            product_type,
        )
        return {key: list(values) for key, values in self._EMPTY_DIMENSIONS.items()}
    
    def _pool_by_compat(
        self,
        scene: dict,
        compat_key: str,
        all_items: list,
        unrestricted_fallback=None,
    ) -> list:
        """按场景上的兼容三态筛选候选。空 allowlist = 都不兼容，不回退。"""
        items = all_items or []
        mode = scene.get(f"compatible_{compat_key}_mode") or "unrestricted"
        id_set = set(scene.get(f"compatible_{compat_key}", []) or [])

        if mode == "allowlist":
            return [x for x in items if x.get("id") in id_set]
        if mode == "blocklist":
            pool = [x for x in items if x.get("id") not in id_set]
            return pool if pool else list(items)

        if unrestricted_fallback is not None:
            pool = unrestricted_fallback()
        else:
            pool = list(items)
        return pool if pool else list(items)

    def _select_scene(self, product_type: str = "Night Lights", db=None) -> dict:
        """选择一个场景"""
        dimensions = self._get_dimensions(product_type, db)
        scenes = dimensions.get("scenes") or []
        if not scenes:
            return {"id": "default", "name": "默认场景"}
        return random.choice(scenes)
    
    def _select_lighting(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的光线"""
        dimensions = self._get_dimensions(product_type, db)
        lighting = dimensions.get("lighting") or []

        def unrestricted():
            # 无显式 mode 且带有旧式白名单 id 时，按白名单处理（静态 DIMENSIONS）
            if scene.get("compatible_lighting") and not scene.get("compatible_lighting_mode"):
                ids = set(scene["compatible_lighting"])
                return [light for light in lighting if light.get("id") in ids]
            scene_time = scene.get("time", "day")
            return [
                light for light in lighting
                if light.get("time") == scene_time or light.get("time") is None
            ]

        compatible_lighting = self._pool_by_compat(scene, "lighting", lighting, unrestricted)
        if not compatible_lighting:
            return {"id": "default", "name": "默认光线"}
        return random.choice(compatible_lighting)
    
    def _select_style(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的风格"""
        dimensions = self._get_dimensions(product_type, db)
        styles = dimensions.get("styles") or []

        def unrestricted():
            if scene.get("compatible_styles") and not scene.get("compatible_styles_mode"):
                ids = set(scene["compatible_styles"])
                return [style for style in styles if style.get("id") in ids]
            scene_id = scene.get("id")
            return [
                style for style in styles
                if not style.get("compatible_with") or scene_id in style["compatible_with"]
            ]

        compatible_styles = self._pool_by_compat(scene, "styles", styles, unrestricted)
        if not compatible_styles:
            return {"id": "default", "name": "默认风格"}
        return random.choice(compatible_styles)
    
    def _select_details(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的细节/道具"""
        dimensions = self._get_dimensions(product_type, db)
        details = dimensions.get("details") or []

        def unrestricted():
            if scene.get("compatible_details") and not scene.get("compatible_details_mode"):
                ids = set(scene["compatible_details"])
                return [detail for detail in details if detail.get("id") in ids]
            scene_id = scene.get("id")
            return [
                detail for detail in details
                if not detail.get("compatible_with") or scene_id in detail["compatible_with"]
            ]

        compatible_details = self._pool_by_compat(scene, "details", details, unrestricted)
        if not compatible_details:
            return {"id": "default", "name": "默认细节"}
        return random.choice(compatible_details)
    
    def _select_viewpoint(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的视角"""
        dimensions = self._get_dimensions(product_type, db)
        viewpoints = dimensions.get("viewpoints") or []

        def unrestricted():
            if scene.get("compatible_viewpoints") and not scene.get("compatible_viewpoints_mode"):
                ids = set(scene["compatible_viewpoints"])
                return [v for v in viewpoints if v.get("id") in ids]
            return list(viewpoints)

        compatible_viewpoints = self._pool_by_compat(scene, "viewpoints", viewpoints, unrestricted)
        if not compatible_viewpoints:
            return {"id": "default", "name": "默认视角"}
        return random.choice(compatible_viewpoints)
    
    def _select_composition(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的构图"""
        dimensions = self._get_dimensions(product_type, db)
        compositions = dimensions.get("compositions") or []

        def unrestricted():
            if scene.get("compatible_compositions") and not scene.get("compatible_compositions_mode"):
                ids = set(scene["compatible_compositions"])
                return [c for c in compositions if c.get("id") in ids]
            return list(compositions)

        compatible_compositions = self._pool_by_compat(
            scene, "compositions", compositions, unrestricted
        )
        if not compatible_compositions:
            return {"id": "default", "name": "默认构图"}
        return random.choice(compatible_compositions)
    
    def _select_quality(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的画质"""
        dimensions = self._get_dimensions(product_type, db)
        qualities = dimensions.get("quality") or []

        def unrestricted():
            if scene.get("compatible_quality") and not scene.get("compatible_quality_mode"):
                ids = set(scene["compatible_quality"])
                return [q for q in qualities if q.get("id") in ids]
            return list(qualities)

        compatible_qualities = self._pool_by_compat(scene, "quality", qualities, unrestricted)
        if not compatible_qualities:
            return {"id": "default", "name": "默认画质"}
        return random.choice(compatible_qualities)
    
    def _select_dimensions(self, product_type: str = "Night Lights", db=None) -> dict:
        """基于规则选择所有维度，确保兼容性"""
        # 1. 先选择场景
        scene = self._select_scene(product_type, db)
        
        # 2. 根据场景选择兼容的光线
        lighting = self._select_lighting(scene, product_type, db)
        
        # 3. 根据场景选择兼容的风格
        style = self._select_style(scene, product_type, db)
        
        # 4. 根据场景选择兼容的细节
        details = self._select_details(scene, product_type, db)
        
        # 5. 根据场景选择兼容的视角、构图、画质
        viewpoint = self._select_viewpoint(scene, product_type, db)
        composition = self._select_composition(scene, product_type, db)
        quality = self._select_quality(scene, product_type, db)
        
        return {
            "scene": scene,
            "viewpoint": viewpoint,
            "composition": composition,
            "style": style,
            "quality": quality,
            "details": details,
            "lighting": lighting
        }
    
    def build_copywriting_prompt(self, product_info: Dict, platform: str, db=None) -> str:
        platform_style = PLATFORM_STYLES.get(platform, PLATFORM_STYLES["instagram"])
        
        selling_points = product_info.get('selling_points', [])
        if selling_points is None:
            selling_points = []
        if isinstance(selling_points, str):
            selling_points = selling_points.split(",")
        
        selling_points = [sp.strip() for sp in selling_points if sp.strip()]
        
        if not selling_points:
            selling_points = ["高品质产品", "全球父母信赖"]
        
        num_points = random.randint(1, min(2, len(selling_points)))
        selected_points = random.sample(selling_points, num_points)
        selling_points_str = "\n".join([f"- {sp}" for sp in selected_points])
        
        narrative_perspective = random.choice(NARRATIVE_PERSPECTIVES)
        writing_style = random.choice(WRITING_STYLES)
        
        prompt = f"""
为 {platform.upper()} 创建英文社交媒体帖子，需严格遵守以下要求：

产品信息：
- 名称：{product_info.get('product_name', '')}
- 描述：{product_info.get('description', '')}

核心卖点（选择1-2个突出）：
{selling_points_str}

风格指导：
- 叙事视角：{narrative_perspective['name']} - {narrative_perspective['description']}
- 写作风格：{writing_style['name']} - {writing_style['description']}
- 品牌调性：{product_info.get('brand_voice', '专业且温暖')}

强制规则（必须全部遵守！）：
1. 长度：必须为120-200字（包含所有文本和话题标签）
2. 表情符号：使用4-6个相关表情符号（🌙🍼✨🤍💤等）
3. 格式：简短段落（每段1-2句话），段落间换行
4. 禁止：加粗(**文字**)、斜体(*文字*)、标题、列表、项目符号
5. 结尾包含2-5个话题标签
6. 匹配选定的叙事视角和写作风格

示例格式：
Nighttime just got sweeter with our baby monitor! 🌙
No WiFi, no radiation—just pure peace of mind. ✨
Clip it anywhere, calm anytime. 🍼
#BabyEssentials #SafeSleep

仅输出帖子内容，无需其他文字。
"""
        return prompt.strip()

    def build_image_prompt(self, product_info: Dict, platform: str, style_hint: Optional[str] = None, db=None) -> Dict:
        product_name = product_info.get('product_name', '产品')
        product_description = product_info.get('description', '')
        category = product_info.get('category', '')
        product_type = (product_info.get('product_type') or category or 'Night Lights').strip()
        
        selling_points = product_info.get('selling_points', [])
        if selling_points is None:
            selling_points = []
        if isinstance(selling_points, str):
            selling_points = selling_points.split(",")
        
        selling_points = [sp.strip() for sp in selling_points if sp.strip()]
        selling_points_str = ", ".join(selling_points) if selling_points else "高品质婴儿产品"
        
        selected_dimensions = self._select_dimensions(product_type, db)
        
        nunito_constraint = ""
        if 'Nunito' in product_description or 'nunito' in product_description:
            nunito_constraint = (
                "5. 产品上印有 bebcare 字符时，必须以 Nunito 字体呈现，且不得额外生成其它文字"
            )
        
        prompt = f"""
## 产品信息：
- 名称：{product_name}
- 描述：{product_description}
- 核心卖点：{selling_points_str}

## 选定维度：
- 场景：{selected_dimensions['scene']['name']}
- 视角：{selected_dimensions['viewpoint']['name']}
- 构图：{selected_dimensions['composition']['name']}
- 风格：{selected_dimensions['style']['name']}
- 画质：{selected_dimensions['quality']['name']}
- 细节/道具：{selected_dimensions['details']['name']}
- 光线：{selected_dimensions['lighting']['name']}

## 硬约束（必须遵守，优先级高于风格与氛围；写入最终中文提示词）
1. 产品外形、结构、部件数量与相对位置不可改变；有参考图时，外观以参考图为准
2. 产品颜色、材质、纹理、印刷/标识必须与描述一致，禁止改色、变形、缺失或多余部件
3. 画面中禁止生成文字、水印、二维码、网址、字幕或额外品牌名（产品自带印刷除外）
4. 禁止无关产品入画；道具不得遮挡或改变产品主体
{nunito_constraint}

## 输出要求
- 仅输出一段最终中文图像提示词
- 先写产品保真描述，再融合场景/光线/构图/风格/画质/细节
"""
        
        dimensions_info = {
            "scene": selected_dimensions['scene']['name'],
            "viewpoint": selected_dimensions['viewpoint']['name'],
            "composition": selected_dimensions['composition']['name'],
            "style": selected_dimensions['style']['name'],
            "quality": selected_dimensions['quality']['name'],
            "details": selected_dimensions['details']['name'],
            "lighting": selected_dimensions['lighting']['name']
        }
        
        return {
            "prompt": prompt.strip(),
            "dimensions": dimensions_info
        }

    def build_negative_prompt(self) -> str:
        hard_rules = ", ".join(NEGATIVE_PROMPT["hard_rules"])
        soft_rules = ", ".join(NEGATIVE_PROMPT["soft_suggestions"])
        
        return f"{hard_rules}, {soft_rules}"

    def build_scene_reference_prompt(self, product_info: Dict, platform: str, style_hint: Optional[str] = None, db=None) -> Dict:
        product_name = product_info.get('product_name', '产品')
        category = product_info.get('category', '')
        product_type = (product_info.get('product_type') or category or 'Night Lights').strip()

        selected_dimensions = self._select_dimensions(product_type, db)
        dimensions_info = {
            "scene": "参考场景图",
            "viewpoint": "沿用参考图",
            "composition": "沿用参考图",
            "style": selected_dimensions['style']['name'],
            "quality": selected_dimensions['quality']['name'],
            "details": selected_dimensions['details']['name'],
            "lighting": selected_dimensions['lighting']['name'],
        }

        prompt = f"""
将后面的{product_name}图片融合到场景中，保持产品主体的位置、角度、大小、外观完全不变。

## 硬约束（必须遵守）
1. 保持产品的位置、角度、大小、外观完全不变
2. 保持产品的颜色、材质、纹理细节完全不变
3. 保持原场景的构图结构和布局基本不变
4. 保持原图像的光线方向和整体色调一致
5. 仅对背景进行轻微优化，避免过度改动
6. 画面中禁止生成文字、水印、二维码、网址或额外品牌名
7. 若场景参考图中出现其他产品，使用本次提供的{product_name}将其替换

## 软引导（不得违反硬约束）
- 风格倾向：{dimensions_info['style']}
- 画质倾向：{dimensions_info['quality']}
- 可轻微增加的细节/道具：{dimensions_info['details']}（不得遮挡或改变产品）

## 优先级
1）产品保真 → 2）场景结构保真 → 3）风格/画质/细节软引导
"""

        return {
            "prompt": prompt.strip(),
            "dimensions": dimensions_info,
        }


prompt_engine = PromptEngine()
