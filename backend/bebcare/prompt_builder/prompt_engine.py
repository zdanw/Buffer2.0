from typing import List, Dict, Optional
import json
import random

DIMENSIONS = {
    "scenes": [
        "Cozy nursery corner with wooden crib",
        "Soft dim baby bedside with sleeping baby",
        "Hanging on baby stroller during park walk",
        "On nightstand next to baby bottle and swaddle",
        "Travel hotel room with portable crib",
        "Living room play mat during parent-child time",
        "Next to nursing chair in dim light",
        "Hanging on car seat handle"
    ],
    "viewpoints": [
        "Eye-level close-up at 45-degree angle showing product front",
        "Top-down view with product lying on soft fabric",
        "Ultra-low angle simulating baby's view of glowing base",
        "Selfie perspective with parent holding product",
        "Side view showing product thickness and details",
        "Macro close-up focusing on light diffuser and buttons",
        "POV from stroller handle looking back"
    ],
    "compositions": [
        "Rule of thirds with product at lower right, soft light left",
        "Central symmetry with product surrounded by lullaby notes",
        "Foreground blur through crib rails focusing on product",
        "Diagonal composition with hanging strap as leading line",
        "Full-frame composition showing multi-color gradient",
        "Minimalist with large negative space",
        "Narrative composition with product and sleeping baby (partial)"
    ],
    "styles": [
        "Minimalist Nordic baby aesthetic with soft matte texture",
        "Warm documentary family photography with film grain",
        "Dreamy soft focus art style with bokeh background",
        "Lifestyle style with natural light in real home setting"
    ],
    "quality": [
        "8K ultra-high resolution with clear material texture",
        "Cinema-grade lighting with natural depth of field",
        "C4D render quality with detailed silicone and plastic",
        "Macro photography with visible matte surface",
        "High dynamic range with rich light halo layers"
    ],
    "details": [
        "Organic cotton plush toy and knitted blanket",
        "Open baby cloth book and wooden rattle",
        "Warm milk cup and half-folded muslin swaddle",
        "Star and moon ornaments with small fiddle-leaf fig",
        "Baby's tiny hand or feet (no face visible)",
        "Scattered musical note paper crafts",
        "Thermometer and baby monitor"
    ],
    "lighting": [
        "Product as sole light source emitting warm orange glow",
        "Soft morning window light with faint warm night light",
        "Backlit golden rim light with product in shadow",
        "Warm table lamp side light for bedtime reading",
        "Complete darkness with only product's soothing light",
        "Golden hour light through curtain gaps"
    ]
}

NEGATIVE_PROMPT = {
    "hard_rules": [
        "watermark", "text", "QR code", "URL", "website",
        "trademark", "logo", "brand name", "label", "border",
        "badge", "platform logo", "product shape altered",
        "unrelated products", "color tampering", "missing parts",
        "blurry", "distorted", "low quality", "ugly"
    ],
    "soft_suggestions": [
        "avoid repetitive composition",
        "avoid similar backgrounds",
        "avoid matching color tones",
        "avoid clutter"
    ]
}

PLATFORM_STYLES = {
    "instagram": {
        "tone": "elegant, sophisticated, emotional",
        "length": "medium",
        "emoji_ratio": 0.3
    },
    "tiktok": {
        "tone": "playful, energetic, rhythmic",
        "length": "short",
        "emoji_ratio": 0.5
    },
    "facebook": {
        "tone": "detailed, warm, trustworthy",
        "length": "long",
        "emoji_ratio": 0.1
    }
}

NARRATIVE_PERSPECTIVES = [
    {"id": "tech_reviewer", "name": "Tech Reviewer", "description": "Professional, technical review style"},
    {"id": "busy_mom", "name": "Busy Mom", "description": "Authentic, relatable mom perspective"},
    {"id": "humorist", "name": "Humorist", "description": "Lighthearted, funny approach"},
    {"id": "tech_blogger", "name": "Tech Blogger", "description": "Cutting-edge, professional tech analysis"},
    {"id": "lifestyle", "name": "Lifestyle Aesthete", "description": "Elegant, refined lifestyle"},
    {"id": "new_parent", "name": "New Parents", "description": "Genuine, down-to-earth parenting"}
]

WRITING_STYLES = [
    {"id": "种草风", "name": "Grassroots Style", "description": "Friendly, recommendation-style copy"},
    {"id": "理性分析", "name": "Rational Analysis", "description": "In-depth, logical analysis"},
    {"id": "温情故事", "name": "Warm Story", "description": "Heartwarming, storytelling"},
    {"id": "硬核测评", "name": "Hardcore Review", "description": "Professional, objective review"},
    {"id": "幽默搞笑", "name": "Humorous", "description": "Light, funny style"},
    {"id": "情感共鸣", "name": "Emotional Resonance", "description": "Touching, emotional copy"}
]


class PromptEngine:
    def __init__(self):
        self.system_prompt = """
You are a professional marketing expert for Bebcare, a premium baby brand. 
You specialize in creating high-quality English social media copy and image prompts.

Follow these principles:
1. Maintain a professional yet warm tone appropriate for baby products
2. Highlight product core selling points
3. Use appropriate emojis to enhance emotional expression
4. Ensure content fits target platform characteristics
5. Image prompts must include detailed scene, lighting, and composition descriptions
6. Output ONLY in English
"""

    def build_copywriting_prompt(self, product_info: Dict, platform: str) -> str:
        platform_style = PLATFORM_STYLES.get(platform, PLATFORM_STYLES["instagram"])
        
        # 智能提取卖点列表
        core_selling_points = self._extract_selling_points(product_info)
        
        # 随机选择1-2个卖点用于本次生成
        num_points = random.randint(1, min(2, len(core_selling_points)))
        selected_points = random.sample(core_selling_points, num_points)
        selling_points_str = "\n".join([f"- {sp}" for sp in selected_points])
        
        # 随机选择叙事视角和写作风格
        narrative_perspective = random.choice(NARRATIVE_PERSPECTIVES)
        writing_style = random.choice(WRITING_STYLES)
        
        prompt = f"""
Create an English social media post for {platform.upper()} with these EXACT requirements:

PRODUCT INFO:
- Name: {product_info.get('product_name', '')}
- Description: {product_info.get('description', '')}

KEY SELLING POINTS (choose 1-2 to highlight):
{selling_points_str}

STYLE GUIDANCE:
- Narrative Perspective: {narrative_perspective['name']} - {narrative_perspective['description']}
- Writing Style: {writing_style['name']} - {writing_style['description']}
- Brand Tone: {product_info.get('brand_voice', 'Professional and Warm')}

MANDATORY RULES (FOLLOW ALL!):
1. LENGTH: MUST be 500-800 characters (count includes all text and hashtags)
2. EMOJIS: USE 4-6 RELEVANT emojis throughout (🌙🍼✨🤍💤 etc.)
3. FORMAT: Short paragraphs (1-2 sentences each), line breaks between them
4. NO bold (**text**), NO italics (*text*), NO headings, NO lists, NO bullet points
5. INCLUDE 2-3 hashtags at the end
6. Match the selected narrative perspective and writing style

WRITE LIKE THIS EXAMPLE:
Nighttime just got sweeter with our baby monitor! 🌙
No WiFi, no radiation—just pure peace of mind. ✨
Clip it anywhere, calm anytime. 🍼
#BabyEssentials #SafeSleep

Output ONLY the post content.
"""
        return prompt.strip()

    def _extract_selling_points(self, product_info: Dict) -> List[str]:
        """
        智能提取产品卖点
        
        策略：
        1. 从产品描述中识别关键功能特性
        2. 根据识别的特性动态生成卖点
        3. 保持卖点简洁、有吸引力
        """
        description = product_info.get('description', '').lower()
        product_name = product_info.get('product_name', '').lower()
        tags = product_info.get('tags', [])
        
        selling_points = []
        
        # 定义特性关键词映射表（更全面的映射）
        feature_keywords = {
            # 安全相关
            ("wifi-free", "no wifi", "low radiation", "radiation-free"): 
                ("Safe WiFi-free design", "No harmful radiation, protecting baby's health"),
            ("cry detection", "crying", "cry sensor"): 
                ("Smart cry detection", "Responds to baby's needs instantly"),
            ("temperature", "room temp", "thermal"):
                ("Temperature monitoring", "Real-time room temp display"),
            
            # 功能相关
            ("music", "lullaby", "lullabies", "songs", "melodies"):
                ("Soothing music", "Play lullabies to help baby drift off to sleep"),
            ("night light", "nightlight", "glow", "soft light", "multi-colored"):
                ("Gentle night light", "Soft multi-colored glow for peaceful sleep"),
            ("rechargeable", "usb-c", "usb c", "battery"):
                ("Rechargeable battery", "USB-C charging, cordless convenience"),
            ("portable", "clip", "hang", "travel", "stroller"):
                ("Portable design", "Easy to clip on stroller or crib"),
            ("timer", "auto play", "auto"):
                ("Auto timer", "Music timer for peace of mind"),
            ("volume", "adjustable"):
                ("Adjustable volume", "Perfect sound level for baby"),
            ("shuffle", "repeat"):
                ("Multiple play modes", "Shuffle and repeat functions"),
            ("monitor", "camera", "baby monitor"):
                ("Baby monitor", "Keep an eye on baby anytime"),
            
            # 材质/设计相关
            ("silicone", "plastic", "material", "texture"):
                ("Premium materials", "Safe silicone and quality plastic"),
            ("compact", "mini", "small", "tiny"):
                ("Compact design", "Cute and space-saving"),
            ("soft", "gentle", "comfy"):
                ("Soft & gentle", "Comfortable for baby"),
        }
        
        # 扫描描述中的特性
        found_features = []
        for keywords, (title, desc) in feature_keywords.items():
            if any(kw in description for kw in keywords):
                if title not in [f[0] for f in found_features]:
                    found_features.append((title, desc))
        
        # 如果找到足够的特性，添加前3个作为卖点
        if found_features:
            selling_points = [desc for title, desc in found_features[:3]]
        else:
            # 如果没有找到特定特性，使用通用卖点
            if "baby" in product_name or "baby" in description:
                selling_points = [
                    "Premium baby product",
                    "Designed for parents who care",
                    "High-quality and safe"
                ]
            else:
                selling_points = [
                    "High-quality product",
                    "Professional grade",
                    "Excellent performance"
                ]
        
        # 如果卖点太少，添加一个通用卖点
        if len(selling_points) < 2:
            selling_points.append("Trusted by parents worldwide")
        
        return selling_points

    def build_image_prompt(self, product_info: Dict, platform: str, style_hint: Optional[str] = None) -> str:
        product_name = product_info.get('product_name', 'product')
        product_description = product_info.get('description', '')
        
        scenes_str = ", ".join(DIMENSIONS["scenes"])
        viewpoints_str = ", ".join(DIMENSIONS["viewpoints"])
        compositions_str = ", ".join(DIMENSIONS["compositions"])
        styles_str = ", ".join(DIMENSIONS["styles"])
        quality_str = ", ".join(DIMENSIONS["quality"])
        details_str = ", ".join(DIMENSIONS["details"])
        lighting_str = ", ".join(DIMENSIONS["lighting"])
        
        prompt = f"""
You are a professional AI image prompt generator. Based on the product information provided, select appropriate options from the following dimensions to create a high-quality Chinese image prompt.

## Product Information:
- Name: {product_name}
- Description: {product_description}

## Dimension Options:
- Scenes: {scenes_str}
- Viewpoints: {viewpoints_str}
- Compositions: {compositions_str}
- Styles: {styles_str}
- Quality: {quality_str}
- Details/Props: {details_str}
- Lighting: {lighting_str}

## Requirements:
1. Output in Chinese only.

2. Select one option from each of the seven dimensions.

3. Naturally integrate the selected options to generate a high-quality prompt for the image.

4. Maintain a professional photographic style.

5. If the selected options contradict each other, make appropriate modifications to ensure the final image is realistic and natural.

Output format: Directly output the image prompt without any additional content.
"""
        
        if style_hint:
            prompt += f"\n\nStyle Hint: {style_hint}"
        
        return prompt.strip()

    def build_negative_prompt(self) -> str:
        hard_rules = ", ".join(NEGATIVE_PROMPT["hard_rules"])
        soft_rules = ", ".join(NEGATIVE_PROMPT["soft_suggestions"])
        
        return f"{hard_rules}, {soft_rules}"

    def build_scene_reference_prompt(self, product_info: Dict, platform: str, style_hint: Optional[str] = None) -> str:
        product_name = product_info.get('product_name', 'product')
        appearance = product_info.get('description', '')
        
        prompt = f"""
Use the first image as background scene reference.
Reference the product appearance and details from subsequent images.
Naturally place {product_name} into the scene.
Product appearance features: {appearance}
Maintain the scene's atmosphere and lighting style.
Preserve product details and texture.
Ensure seamless integration between product and scene, realistic and natural.
Quality: 8K, commercial photography, sharp focus, high detail, realistic rendering.

Output in English ONLY.
"""
        
        if style_hint:
            prompt += f"\nStyle Hint: {style_hint}"
        
        return prompt.strip()


prompt_engine = PromptEngine()