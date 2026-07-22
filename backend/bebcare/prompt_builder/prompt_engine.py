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

    def _get_dimensions(self, product_type: str = "Night Lights", db=None) -> dict:
        """获取指定产品类型的维度配置"""
        if db is not None and dimension_service is not None:
            try:
                result = dimension_service.get_dimensions_by_product_type(product_type, db)
                return result
            except Exception as e:
                logger.exception('dimension_service.get_dimensions_by_product_type failed: %s', e)
        
        if product_type not in DIMENSIONS:
            logger.warning("Product type '%s' not found in DIMENSIONS, falling back to 'Night Lights'", product_type)
        
        return DIMENSIONS.get(product_type, DIMENSIONS["Night Lights"])
    
    def _select_scene(self, product_type: str = "Night Lights", db=None) -> dict:
        """选择一个场景"""
        dimensions = self._get_dimensions(product_type, db)
        return random.choice(dimensions["scenes"])
    
    def _select_lighting(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的光线"""
        dimensions = self._get_dimensions(product_type, db)
        compatible_lighting_ids = scene.get("compatible_lighting", [])
        
        if compatible_lighting_ids:
            compatible_lighting = [
                light for light in dimensions["lighting"]
                if light.get("id") in compatible_lighting_ids
            ]
        else:
            scene_time = scene.get("time", "day")
            compatible_lighting = [
                light for light in dimensions["lighting"]
                if light.get("time") == scene_time or light.get("time") is None
            ]
        
        if not compatible_lighting:
            compatible_lighting = dimensions["lighting"]
        
        if not compatible_lighting:
            return {"id": "default", "name": "默认光线"}
        
        return random.choice(compatible_lighting)
    
    def _select_style(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的风格"""
        dimensions = self._get_dimensions(product_type, db)
        compatible_style_ids = scene.get("compatible_styles", [])
        
        if compatible_style_ids:
            compatible_styles = [
                style for style in dimensions["styles"]
                if style.get("id") in compatible_style_ids
            ]
        else:
            scene_id = scene.get("id")
            compatible_styles = [
                style for style in dimensions["styles"]
                if not style.get("compatible_with") or scene_id in style["compatible_with"]
            ]
        
        if not compatible_styles:
            compatible_styles = dimensions["styles"]
        
        if not compatible_styles:
            return {"id": "default", "name": "默认风格"}
        
        return random.choice(compatible_styles)
    
    def _select_details(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的细节/道具"""
        dimensions = self._get_dimensions(product_type, db)
        compatible_detail_ids = scene.get("compatible_details", [])
        
        if compatible_detail_ids:
            compatible_details = [
                detail for detail in dimensions["details"]
                if detail.get("id") in compatible_detail_ids
            ]
        else:
            scene_id = scene.get("id")
            compatible_details = [
                detail for detail in dimensions["details"]
                if not detail.get("compatible_with") or scene_id in detail["compatible_with"]
            ]
        
        if not compatible_details:
            compatible_details = dimensions["details"]
        
        if not compatible_details:
            return {"id": "default", "name": "默认细节"}
        
        return random.choice(compatible_details)
    
    def _select_viewpoint(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的视角"""
        dimensions = self._get_dimensions(product_type, db)
        compatible_viewpoint_ids = scene.get("compatible_viewpoints", [])
        
        if compatible_viewpoint_ids:
            compatible_viewpoints = [
                viewpoint for viewpoint in dimensions["viewpoints"]
                if viewpoint.get("id") in compatible_viewpoint_ids
            ]
        else:
            compatible_viewpoints = dimensions["viewpoints"]
        
        if not compatible_viewpoints:
            compatible_viewpoints = dimensions["viewpoints"]
        
        if not compatible_viewpoints:
            return {"id": "default", "name": "默认视角"}
        
        return random.choice(compatible_viewpoints)
    
    def _select_composition(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的构图"""
        dimensions = self._get_dimensions(product_type, db)
        compatible_composition_ids = scene.get("compatible_compositions", [])
        
        if compatible_composition_ids:
            compatible_compositions = [
                composition for composition in dimensions["compositions"]
                if composition.get("id") in compatible_composition_ids
            ]
        else:
            compatible_compositions = dimensions["compositions"]
        
        if not compatible_compositions:
            compatible_compositions = dimensions["compositions"]
        
        if not compatible_compositions:
            return {"id": "default", "name": "默认构图"}
        
        return random.choice(compatible_compositions)
    
    def _select_quality(self, scene: dict, product_type: str = "Night Lights", db=None) -> dict:
        """根据场景选择兼容的画质"""
        dimensions = self._get_dimensions(product_type, db)
        compatible_quality_ids = scene.get("compatible_quality", [])
        
        if compatible_quality_ids:
            compatible_qualities = [
                quality for quality in dimensions["quality"]
                if quality.get("id") in compatible_quality_ids
            ]
        else:
            compatible_qualities = dimensions["quality"]
        
        if not compatible_qualities:
            compatible_qualities = dimensions["quality"]
        
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
            nunito_constraint = "4. 产品上印有bebcare字符,必须以Nunito字体呈现"
        
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

{nunito_constraint}
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

    def build_scene_reference_prompt(self, product_info: Dict, platform: str, style_hint: Optional[str] = None, db=None) -> str:
        product_name = product_info.get('product_name', '产品')
        appearance = product_info.get('description', '')
        category = product_info.get('category', '')
        
        prompt = f"""
将后面的{product_name}图片融合到场景中，保持产品主体的位置、角度、大小、外观完全不变。
1. 保持产品的位置、角度、大小、外观完全不变
2. 保持产品的颜色、材质、纹理细节完全不变
3. 仅对背景进行轻微优化，使其更符合婴儿房场景风格
4. 保持原场景的构图结构和布局基本不变
5. 保持原图像的光线方向和整体色调一致
6. 背景优化采用柔和自然的婴儿房元素，避免过度改动

"""
        
       
        
        return prompt.strip()


prompt_engine = PromptEngine()
