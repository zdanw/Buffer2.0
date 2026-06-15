from typing import List, Dict, Optional
import json
import random

DIMENSIONS = {
    "default": {
        "scenes": [
            {"id": "nursery", "name": "温馨婴儿房角落配有木质婴儿床", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "bedside", "name": "柔和昏暗的婴儿床边，婴儿正在安睡", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "stroller", "name": "挂在婴儿推车上，在公园散步", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "nightstand", "name": "床头柜上，旁边有奶瓶和襁褓", "time": "night", "lighting": ["warm", "soft"]},
            {"id": "hotel", "name": "旅行酒店房间配有便携式婴儿床", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "livingroom", "name": "客厅游戏垫上，亲子时光", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "nursing", "name": "护理椅旁边，光线昏暗", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "carseat", "name": "挂在汽车座椅扶手上", "time": "day", "lighting": ["natural", "bright"]}
        ],
        "viewpoints": [
            {"id": "eye_level", "name": "平视特写，45度角展示产品正面"},
            {"id": "top_down", "name": "俯视角度，产品躺在柔软面料上"},
            {"id": "low_angle", "name": "超低角度，模拟婴儿视角看发光底座"},
            {"id": "selfie", "name": "自拍视角，父母手持产品"},
            {"id": "side_view", "name": "侧视图，展示产品厚度和细节"},
            {"id": "macro", "name": "微距特写，聚焦于光扩散器和按钮"},
            {"id": "pov", "name": "从推车把手向后看的视角"}
        ],
        "compositions": [
            {"id": "rule_of_thirds", "name": "三分构图，产品在右下方，柔光在左侧"},
            {"id": "symmetry", "name": "中心对称，产品被摇篮曲音符环绕"},
            {"id": "foreground_blur", "name": "前景模糊（透过婴儿床栏杆），聚焦产品"},
            {"id": "diagonal", "name": "对角线构图，挂绳作为引导线"},
            {"id": "full_frame", "name": "全画幅构图，展示多色渐变"},
            {"id": "minimalist", "name": "极简主义，大量留白"},
            {"id": "narrative", "name": "叙事构图，产品和熟睡婴儿（部分可见）"}
        ],
        "styles": [
            {"id": "nordic", "name": "简约北欧婴儿美学，柔和哑光质感", "compatible_with": ["nursery", "bedside", "nightstand"]},
            {"id": "documentary", "name": "温暖纪实家庭摄影风格，带有胶片颗粒", "compatible_with": ["livingroom", "nursing", "stroller"]},
            {"id": "dreamy", "name": "梦幻柔焦艺术风格，背景虚化", "compatible_with": ["bedside", "nursery", "hotel"]},
            {"id": "lifestyle", "name": "生活方式风格，自然光真实居家场景", "compatible_with": ["livingroom", "stroller", "carseat"]}
        ],
        "quality": [
            {"id": "8k", "name": "8K超高分辨率，清晰材质纹理"},
            {"id": "cinematic", "name": "影院级灯光，自然景深"},
            {"id": "c4d", "name": "C4D渲染品质，精细硅胶和塑料材质"},
            {"id": "macro_photo", "name": "微距摄影，可见哑光表面"},
            {"id": "hdr", "name": "高动态范围，丰富光晕层次"}
        ],
        "details": [
            {"id": "toys", "name": "有机棉毛绒玩具和针织毯", "compatible_with": ["nursery", "livingroom"]},
            {"id": "book", "name": "打开的婴儿布书和木质摇铃", "compatible_with": ["nursery", "bedside"]},
            {"id": "feeding", "name": "温热的牛奶杯和半折叠的纱布襁褓", "compatible_with": ["bedside", "nightstand"]},
            {"id": "decor", "name": "星星月亮装饰品和小型琴叶榕", "compatible_with": ["nursery", "hotel"]},
            {"id": "baby_parts", "name": "婴儿的小手或小脚（无面部）", "compatible_with": ["bedside", "nursing"]},
            {"id": "music", "name": "散落的音符纸艺", "compatible_with": ["nursery", "livingroom"]},
            {"id": "monitor", "name": "温度计和婴儿监护仪", "compatible_with": ["nightstand", "bedside"]}
        ],
        "lighting": [
            {"id": "product_glow", "name": "产品作为唯一光源，发出温暖橙色光芒", "time": "night"},
            {"id": "morning", "name": "柔和的早晨窗户光线，带有微弱暖色夜灯", "time": "day"},
            {"id": "backlight", "name": "背光金色边缘光，产品在阴影中", "time": "day"},
            {"id": "table_lamp", "name": "温暖台灯侧光，适合睡前阅读", "time": "night"},
            {"id": "darkness", "name": "完全黑暗，只有产品的柔和光线", "time": "night"},
            {"id": "golden_hour", "name": "金色时刻光线透过窗帘缝隙", "time": "day"}
        ]
    },
    "audio_monitor": {
        "scenes": [
            {"id": "nursery", "name": "温馨原木风婴儿房，白色婴儿床摆放婴儿端监护主机", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "bedside_night", "name": "主卧床头柜，家长端主机放在床头，婴儿在隔壁婴儿房熟睡", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "stroller_outdoor", "name": "婴儿推车置物篮放置婴儿端监护器，户外公园遛娃场景", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "nightstand_nursery", "name": "婴儿房原木床头柜，监护主机旁摆放恒温奶瓶、纯棉襁褓包巾", "time": "night", "lighting": ["warm", "soft"]},
            {"id": "hotel_travel", "name": "旅行酒店客房便携婴儿床旁，摆放双主机，展现外出带娃便携看护", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "livingroom_play", "name": "客厅爬行游戏垫，家长在客厅做家务，婴儿端放置在儿童围栏内", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "nursing_chair", "name": "婴儿房哺乳懒人椅旁，昏暗睡前哄睡场景，实时监测宝宝动静", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "car_travel", "name": "车载出行，婴儿端固定在儿童安全座椅侧边，家长端放在中控扶手", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "kitchen_housework", "name": "厨房料理台，家长端放在台面，一边做饭一边远程监听婴儿房声音", "time": "day", "lighting": ["natural", "soft"]}
        ],
        "viewpoints": [
            {"id": "eye_level_45", "name": "45°平视产品特写，双主机并排摆放，清晰展示家长端温度显示屏与婴儿端机身bebcare标识"},
            {"id": "top_down_flatlay", "name": "俯拍平铺视角，两台白色监护主机铺在针织婴儿盖毯上，搭配母婴小道具"},
            {"id": "baby_low_angle", "name": "婴儿平视低角度，仰拍放置在婴儿床边的婴儿端主机，凸显近距离收音设计"},
            {"id": "parent_selfie", "name": "第一人称自拍视角，一只手握着带显示屏的家长端，背景可见熟睡的宝宝（仅露出小手小脚）"},
            {"id": "side_profile", "name": "产品侧视角，同时拍摄两台主机侧面，展示机身轻薄便携的厚度、按键与充电接口细节"},
            {"id": "macro_detail", "name": "微距特写，聚焦家长端LED温度显示屏、婴儿端收音麦克风开孔与机身功能按键"},
            {"id": "pov_kitchen", "name": "厨房第一视角，镜头看向料理台的家长端主机，背景虚化露出婴儿房房门"},
            {"id": "dual_hand_hold", "name": "双手手持视角，一只手托举婴儿端主机，另一只手握持带屏幕的家长端主机，直观展示一整套监护设备"}
        ],
        "compositions": [
            {"id": "rule_of_thirds", "name": "三分构图，双主机放置画面右下区域，左侧留白搭配柔和环境光影，突出居家氛围感"},
            {"id": "symmetry_dual", "name": "中心对称构图，婴儿端、家长端左右对称摆放，体现成对配套设计，干净高级"},
            {"id": "foreground_blur_crib", "name": "前景虚化构图，透过婴儿床木质栏杆对焦两台监护主机，营造守护氛围感"},
            {"id": "diagonal_guide", "name": "对角线构图，从婴儿房门延伸至床头柜的监护主机，强化居家远程看护叙事感"},
            {"id": "minimal_white_space", "name": "极简留白构图，浅纯色背景，双主机居中摆放，无多余杂物，突出产品简约设计"},
            {"id": "narrative_lifestyle", "name": "生活叙事构图，部分入镜熟睡婴儿+厨房/客厅家长工作场景+两台监护主机，表达安心带娃的产品价值"},
            {"id": "layer_depth", "name": "前后景分层构图，前景家长端主机清晰，背景虚化婴儿房里的婴儿端设备，表现远距离无线监听卖点"}
        ],
        "styles": [
            {"id": "nordic_minimal", "name": "北欧简约母婴美学，哑光白色柔和质感，低饱和原木配色，干净治愈", "compatible_with": ["nursery", "bedside_night", "nightstand_nursery", "hotel_travel"]},
            {"id": "warm_documentary", "name": "家庭纪实胶片摄影风，轻微胶片颗粒感，暖调原生色彩，真实生活化带娃场景", "compatible_with": ["livingroom_play", "nursing_chair", "stroller_outdoor", "kitchen_housework"]},
            {"id": "soft_dreamy", "name": "梦幻柔焦氛围感风格，浅景深背景虚化，暖光晕渲染，适合夜间哄睡场景", "compatible_with": ["bedside_night", "nursery", "nursing_chair", "hotel_travel"]},
            {"id": "real_lifestyle", "name": "写实生活方式摄影，自然日光原生色调，无过度滤镜，还原日常居家、出行带娃真实使用场景", "compatible_with": ["stroller_outdoor", "car_travel", "livingroom_play", "kitchen_housework"]},
            {"id": "commercial_clean", "name": "高端电商产品商业摄影风格，均匀柔光，细腻材质还原，适合产品主图展示", "compatible_with": ["nursery", "nightstand_nursery"]}
        ],
        "quality": [
            {"id": "8k_ultra", "name": "8K超高清分辨率，精准还原哑光塑料机身、屏幕LED发光纹理、麦克风细微开孔细节"},
            {"id": "cinematic_depth", "name": "电影级光影景深，柔和焦外虚化，明暗层次丰富，氛围感拉满"},
            {"id": "c4d_render", "name": "C4D写实三维渲染，细腻的机身磨砂材质、金属包边质感，光影过渡自然柔和"},
            {"id": "macro_pro_photo", "name": "专业微距商业摄影，捕捉机身logo、按键纹路、显示屏像素细节，画质锐利干净"},
            {"id": "hdr_high_dynamic", "name": "HDR高动态范围成像，屏幕背光、环境暖光高光暗部细节完整保留，光晕柔和不刺眼"}
        ],
        "details": [
            {"id": "nursery_toys", "name": "针织安抚玩偶、纯棉盖毯、原木婴儿摇铃，温馨婴儿房软装道具", "compatible_with": ["nursery", "livingroom_play"]},
            {"id": "baby_gear", "name": "婴儿布艺绘本、硅胶安抚奶嘴、棉麻收纳筐，生活化母婴小物件", "compatible_with": ["nursery", "bedside_night", "nightstand_nursery"]},
            {"id": "night_supplies", "name": "恒温玻璃奶瓶、折叠纱布襁褓、婴儿保湿面霜，夜间育儿常用用品", "compatible_with": ["bedside_night", "nightstand_nursery", "nursing_chair"]},
            {"id": "travel_baby_bag", "name": "大容量母婴双肩包、便携折叠隔尿垫，出行带娃道具，突出产品便携属性", "compatible_with": ["stroller_outdoor", "hotel_travel", "car_travel"]},
            {"id": "baby_part_detail", "name": "熟睡婴儿的小手、小脚局部入镜（不露面部），营造温柔守护的育儿氛围", "compatible_with": ["bedside_night", "nursing_chair", "nursery"]},
            {"id": "household_scene", "name": "厨房陶瓷餐具、布艺围裙、客厅毛绒地毯，生活化居家环境道具", "compatible_with": ["livingroom_play", "kitchen_housework"]}
        ],
        "lighting": [
            {"id": "screen_soft_glow", "name": "家长端显示屏微弱绿色背光作为环境辅助光源，房间弱光夜间氛围", "time": "night"},
            {"id": "morning_window_light", "name": "清晨窗边柔和漫射自然光，搭配微弱卧室暖小夜灯，光线通透温暖", "time": "day"},
            {"id": "gold_edge_backlight", "name": "逆光金色轮廓光，勾勒两台主机金属包边，主体机身柔和明暗对比", "time": "day"},
            {"id": "bedside_table_lamp", "name": "卧室暖光台灯侧逆光，柔和漫射光影，适合睡前夜间看护场景", "time": "night"},
            {"id": "dim_night_ambient", "name": "弱暗卧室环境，仅依靠家长端屏幕微光与远处床头小夜灯照明，安静深夜看护氛围", "time": "night"},
            {"id": "golden_hour_curtain", "name": "黄昏黄金时刻，暖金色阳光透过亚麻窗帘缝隙漫射进房间，温柔氛围感日光", "time": "day"}
        ]
    }
}

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

    def _get_dimensions(self, product_type: str = "default") -> dict:
        """获取指定产品类型的维度配置"""
        return DIMENSIONS.get(product_type, DIMENSIONS["default"])
    
    def _select_scene(self, product_type: str = "default") -> dict:
        """选择一个场景"""
        dimensions = self._get_dimensions(product_type)
        return random.choice(dimensions["scenes"])
    
    def _select_lighting(self, scene: dict, product_type: str = "default") -> dict:
        """根据场景选择兼容的光线"""
        dimensions = self._get_dimensions(product_type)
        scene_time = scene.get("time", "day")
        compatible_lighting = [
            light for light in dimensions["lighting"]
            if light.get("time") == scene_time or light.get("time") is None
        ]
        
        if not compatible_lighting:
            compatible_lighting = dimensions["lighting"]
        
        return random.choice(compatible_lighting)
    
    def _select_style(self, scene: dict, product_type: str = "default") -> dict:
        """根据场景选择兼容的风格"""
        dimensions = self._get_dimensions(product_type)
        scene_id = scene.get("id")
        compatible_styles = [
            style for style in dimensions["styles"]
            if not style.get("compatible_with") or scene_id in style["compatible_with"]
        ]
        
        if not compatible_styles:
            compatible_styles = dimensions["styles"]
        
        return random.choice(compatible_styles)
    
    def _select_details(self, scene: dict, product_type: str = "default") -> dict:
        """根据场景选择兼容的细节/道具"""
        dimensions = self._get_dimensions(product_type)
        scene_id = scene.get("id")
        compatible_details = [
            detail for detail in dimensions["details"]
            if not detail.get("compatible_with") or scene_id in detail["compatible_with"]
        ]
        
        if not compatible_details:
            compatible_details = dimensions["details"]
        
        return random.choice(compatible_details)
    
    def _select_viewpoint(self, product_type: str = "default") -> dict:
        """选择一个视角"""
        dimensions = self._get_dimensions(product_type)
        return random.choice(dimensions["viewpoints"])
    
    def _select_composition(self, product_type: str = "default") -> dict:
        """选择一个构图"""
        dimensions = self._get_dimensions(product_type)
        return random.choice(dimensions["compositions"])
    
    def _select_quality(self, product_type: str = "default") -> dict:
        """选择画质"""
        dimensions = self._get_dimensions(product_type)
        return random.choice(dimensions["quality"])
    
    def _select_dimensions(self, product_type: str = "default") -> dict:
        """基于规则选择所有维度，确保兼容性"""
        # 1. 先选择场景
        scene = self._select_scene(product_type)
        
        # 2. 根据场景选择兼容的光线
        lighting = self._select_lighting(scene, product_type)
        
        # 3. 根据场景选择兼容的风格
        style = self._select_style(scene, product_type)
        
        # 4. 根据场景选择兼容的细节
        details = self._select_details(scene, product_type)
        
        # 5. 选择视角、构图、画质（无特殊兼容性限制）
        viewpoint = self._select_viewpoint(product_type)
        composition = self._select_composition(product_type)
        quality = self._select_quality(product_type)
        
        return {
            "scene": scene,
            "viewpoint": viewpoint,
            "composition": composition,
            "style": style,
            "quality": quality,
            "details": details,
            "lighting": lighting
        }
    
    def build_copywriting_prompt(self, product_info: Dict, platform: str) -> str:
        platform_style = PLATFORM_STYLES.get(platform, PLATFORM_STYLES["instagram"])
        
        selling_points = product_info.get('selling_points', [])
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

    def build_image_prompt(self, product_info: Dict, platform: str, style_hint: Optional[str] = None) -> str:
        product_name = product_info.get('product_name', '产品')
        product_description = product_info.get('description', '')
        category = product_info.get('category', '')
        
        product_type = 'audio_monitor' if category == 'Audio Monitor' else product_info.get('product_type', 'default')
        
        selling_points = product_info.get('selling_points', [])
        
        if isinstance(selling_points, str):
            selling_points = selling_points.split(",")
        
        selling_points = [sp.strip() for sp in selling_points if sp.strip()]
        selling_points_str = ", ".join(selling_points) if selling_points else "高品质婴儿产品"
        
        # 使用内部规则选择维度，确保兼容性
        selected_dimensions = self._select_dimensions(product_type)
        
        # 构建结构化的提示词
        prompt = f"""
你是专业的AI图像提示词润色师。请将以下结构化信息润色为高质量的中文图像提示词。

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

## 要求：
1. 仅输出中文图像提示词，无需其他内容
2. 将以上信息自然融合成流畅的描述
3. 保持专业商业摄影风格


输出格式：直接输出润色后的图像提示词。
"""
        
        if style_hint:
            prompt += f"\n\n额外风格提示：{style_hint}"
        
        return prompt.strip()

    def build_negative_prompt(self) -> str:
        hard_rules = ", ".join(NEGATIVE_PROMPT["hard_rules"])
        soft_rules = ", ".join(NEGATIVE_PROMPT["soft_suggestions"])
        
        return f"{hard_rules}, {soft_rules}"

    def build_scene_reference_prompt(self, product_info: Dict, platform: str, style_hint: Optional[str] = None) -> str:
        product_name = product_info.get('product_name', '产品')
        appearance = product_info.get('description', '')
        
        prompt = f"""
使用第一张图像作为背景场景参考。
从后续图像中参考产品外观和细节。
自然地将{product_name}放置到场景中。
产品外观特征：{appearance}
保持场景的氛围和光线风格。
保留产品细节和纹理。
确保产品与场景无缝融合，真实自然。
画质：8K，商业摄影，锐聚焦，高细节，真实渲染。

仅输出英文。
"""
        
        if style_hint:
            prompt += f"\n风格提示：{style_hint}"
        
        return prompt.strip()


prompt_engine = PromptEngine()