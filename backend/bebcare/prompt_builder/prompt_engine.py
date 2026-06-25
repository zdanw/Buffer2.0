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
    },
    "air_purifier": {
        "scenes": [
            {"id": "crib_nursery", "name": "原木风婴儿床内侧，净化器放置床垫旁，室内居家育儿", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "stroller_outdoor", "name": "婴儿推车扶手挂放净化器，城市公园户外遛娃场景", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "car_seat", "name": "车载儿童安全座椅侧边，车内出行便携净化", "time": "day", "lighting": ["natural", "soft"]},
            {"id": "travel_hotel", "name": "酒店便携折叠婴儿枕边，亲子短途旅行场景", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "living_playmat", "name": "客厅爬行游戏垫角落，宝宝玩耍时放在身边", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "bedside_night", "name": "主卧床头柜，夜间静音运行陪伴宝宝安睡", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "shopping_bag", "name": "帆布母婴包侧袋收纳，随身外出携带场景", "time": "day", "lighting": ["natural", "soft"]},
            {"id": "nursing_armchair", "name": "哺乳懒人椅扶手，昏暗睡前哄睡环境", "time": "night", "lighting": ["dim", "warm"]}
        ],
        "viewpoints": [
            {"id": "eye_45_front", "name": "45°平视正面特写，完整展示顶部微笑卡通线条、正面密集透气小孔与中段通风栅"},
            {"id": "top_down_flatlay", "name": "俯拍平铺构图，奶米白机身平铺针织婴儿毯，展示圆润圆弧顶盖造型"},
            {"id": "baby_low_pov", "name": "婴儿低角度仰拍，模拟宝宝视线看向床边净化器，凸显无尖锐圆角安全设计"},
            {"id": "hand_hold_portable", "name": "单手手持随身视角，手掌托住小巧机身，直观体现轻量化便携尺寸"},
            {"id": "side_profile_cut", "name": "机身侧视图，展现轻薄厚度、底部bebcare标识与分层风道结构"},
            {"id": "macro_filter_detail", "name": "微距特写，聚焦正面密集透气孔、通风栅与机身哑光细腻塑料质感"},
            {"id": "stroller_pov", "name": "推车第一视角，镜头向下看向挂在扶手的净化器，背景虚化户外绿植"}
        ],
        "compositions": [
            {"id": "rule_third", "name": "三分构图，净化器放置画面右下，左侧留白柔和环境光影，突出随身守护氛围感"},
            {"id": "center_symmetry", "name": "中心对称构图，净化器居中放置，四周搭配简约母婴小道具，干净电商主图质感"},
            {"id": "foreground_blur_crib", "name": "前景虚化构图，透过婴儿床原木栏杆对焦净化器，营造婴儿专属防护氛围"},
            {"id": "diagonal_guide", "name": "对角线构图，推车绑带/母婴包肩带作为视觉引导线，突出随身便携属性"},
            {"id": "minimal_blank", "name": "极简留白构图，纯色浅背景，仅放置净化器，弱化杂物凸显简约工业设计"},
            {"id": "narrative_lifestyle", "name": "叙事生活化构图，局部露出熟睡宝宝小手+净化器同框，传递空气防护安心感"},
            {"id": "layer_depth", "name": "前后分层景深，前景清晰净化器，背景模糊宝宝玩耍区域，表达远距离全域净化"}
        ],
        "styles": [
            {"id": "dutch_minimal", "name": "荷兰简约工业母婴美学，低饱和柔和奶白色调，流畅圆润线条，哑光高级质感", "compatible_with": ["crib_nursery", "travel_hotel", "bedside_night"]},
            {"id": "warm_documentary", "name": "家庭纪实胶片摄影，轻微颗粒暖调，真实生活化带娃随身使用场景", "compatible_with": ["stroller_outdoor", "living_playmat", "shopping_bag"]},
            {"id": "soft_dreamy_night", "name": "梦幻柔焦夜景风格，浅景深弱光晕，适配夜间静音净化哄睡场景", "compatible_with": ["bedside_night", "nursing_armchair", "crib_nursery"]},
            {"id": "outdoor_lifestyle", "name": "写实户外生活摄影，原生自然日光，清晰还原随身出行便携使用状态", "compatible_with": ["stroller_outdoor", "car_seat", "shopping_bag"]},
            {"id": "commercial_product", "name": "高端电商商业静物摄影，均匀柔光，精准还原哑光塑料、通风栅、风道细节，适合产品主图", "compatible_with": ["crib_nursery", "living_playmat"]}
        ],
        "quality": [
            {"id": "8k_ultra_detail", "name": "8K超高清，清晰捕捉机身细密透气孔、顶盖简笔微笑线条、底部品牌字体纹理"},
            {"id": "cinematic_bokeh", "name": "电影级景深虚化，柔和自然光影层次，氛围感人像级产品拍摄"},
            {"id": "c4d_product_render", "name": "C4D三维写实渲染，细腻奶米白哑光塑料材质，柔和圆弧曲面光影过渡"},
            {"id": "macro_pro_shot", "name": "专业微距商业摄影，锐利还原通风栅、微孔风道、机身哑光细腻肌理"},
            {"id": "hdr_soft_glow", "name": "HDR高动态范围，明暗层次完整，柔和机身漫反射，无刺眼高光反光"}
        ],
        "details": [
            {"id": "nursery_soft_toys", "name": "针织安抚玩偶、纯棉婴儿盖毯、原木摇铃，温馨婴儿房软装", "compatible_with": ["crib_nursery", "living_playmat"]},
            {"id": "travel_baby_gear", "name": "帆布母婴背包、折叠隔尿垫、便携安抚奶嘴链，出行随身母婴道具", "compatible_with": ["stroller_outdoor", "car_seat", "shopping_bag", "travel_hotel"]},
            {"id": "night_baby_supplies", "name": "玻璃储奶瓶、纱布襁褓、低亮度床头小夜灯，夜间育儿用品", "compatible_with": ["bedside_night", "nursing_armchair", "crib_nursery"]},
            {"id": "air_tech_props", "name": "透明滤网小样、小型空气质量显示卡片，凸显净化黑科技卖点", "compatible_with": ["crib_nursery", "travel_hotel"]},
            {"id": "baby_part_soft", "name": "熟睡婴儿小手、小脚局部入镜（不露面部），柔和治愈亲子氛围", "compatible_with": ["crib_nursery", "bedside_night", "nursing_armchair"]},
            {"id": "household_living", "name": "亚麻窗帘、原木边几、针织爬行垫，简约居家软装", "compatible_with": ["living_playmat", "bedside_night"]}
        ],
        "lighting": [
            {"id": "soft_morning_window", "name": "清晨窗边漫射柔光，通透暖白自然光，搭配微弱室内小夜灯", "time": "day"},
            {"id": "golden_hour_park", "name": "黄昏黄金时刻，树叶缝隙洒落暖金色自然光，户外柔和环境光", "time": "day"},
            {"id": "soft_side_table_lamp", "name": "床头暖光台灯侧漫射光，低亮度柔和漫反射，夜间静音场景", "time": "night"},
            {"id": "dim_night_ambient", "name": "深夜弱暗环境，仅微弱环境小夜灯光，凸显净化器静音夜间运行氛围", "time": "night"},
            {"id": "soft_car_natural", "name": "车内柔和漫射日光，车窗过滤弱化强光，均匀打亮机身哑光表面", "time": "day"},
            {"id": "studio_even_softbox", "name": "影棚柔光箱均匀布光，无硬阴影，商业产品静物专用光线", "time": "all"}
        ]
    },
    "video_motion": {
        "scenes": [
            {"id": "nursery_crib", "name": "温馨婴儿房，云台摄像头正对婴儿床，家长手持显示屏在隔壁房间", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "bedside_night", "name": "主卧床头柜，家长手持显示屏夜间查看宝宝，婴儿房摄像头开启夜视模式", "time": "night", "lighting": ["dim", "infrared"]},
            {"id": "living_room", "name": "客厅，家长在沙发上看电视，同时用显示屏关注卧室里的宝宝", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "yard_stroller", "name": "后院花园，婴儿在推车里睡觉，摄像头固定在推车上，家长在屋内通过显示屏查看", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "playroom_split", "name": "游戏室，一个摄像头对着宝宝，另一个对着玩具区，家长显示屏开启分屏模式", "time": "day", "lighting": ["natural", "soft"]},
            {"id": "hotel_travel", "name": "酒店房间，便携摄像头放在床头柜，家长手持显示屏在浴室门口", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "kitchen_cooking", "name": "厨房，家长一边做饭一边用挂在墙上的显示屏查看宝宝", "time": "day", "lighting": ["natural", "soft"]}
        ],
        "viewpoints": [
            {"id": "dual_device_hero", "name": "产品英雄视角，白色云台摄像头与4.3英寸家长显示屏并排摆放，清晰展示两者外观与屏幕内容"},
            {"id": "camera_pov", "name": "摄像头第一视角，镜头画面即为屏幕上显示的婴儿房实时画面"},
            {"id": "parent_handheld", "name": "家长手持显示屏视角，特写屏幕上宝宝的睡颜，背景是昏暗的卧室"},
            {"id": "baby_low_angle", "name": "婴儿视角，仰拍天花板上的云台摄像头，镜头正下方是宝宝"},
            {"id": "split_screen_detail", "name": "显示屏分屏特写，一个画面是宝宝，另一个画面是客厅"},
            {"id": "nightvision_closeup", "name": "夜视模式特写，摄像头发出微弱红外光，屏幕上显示黑白清晰的宝宝影像"},
            {"id": "wall_mounted_display", "name": "显示屏壁挂视角，固定在厨房或卧室墙上，方便家长随时查看"}
        ],
        "compositions": [
            {"id": "rule_of_thirds", "name": "三分构图，摄像头位于画面一侧，家长手持的显示屏位于另一侧，形成呼应"},
            {"id": "symmetry", "name": "中心对称构图，摄像头与显示屏居中放置，背景干净，适合产品主图"},
            {"id": "foreground_blur", "name": "前景虚化构图，透过婴儿床栏杆或玩具，聚焦于清晰的摄像头或显示屏"},
            {"id": "diagonal_guide", "name": "对角线构图，摄像头的电源线或显示屏的挂绳形成引导线，指向主体"},
            {"id": "narrative", "name": "叙事性构图，捕捉家长在做家务或工作时，瞥一眼显示屏的瞬间"},
            {"id": "minimalist", "name": "极简主义构图，大量留白，仅突出产品本身，强调其简约设计"},
            {"id": "layered_depth", "name": "分层景深构图，前景是家长的手和显示屏，中景是客厅，背景是婴儿房的门，营造空间感"}
        ],
        "styles": [
            {"id": "nordic_minimalist", "name": "北欧简约风格，柔和的白色与原木色，哑光质感，干净治愈", "compatible_with": ["nursery_crib", "bedside_night", "hotel_travel"]},
            {"id": "warm_documentary", "name": "温暖纪实摄影风格，带有轻微胶片颗粒，还原真实的家庭生活场景", "compatible_with": ["living_room", "kitchen_cooking", "yard_stroller"]},
            {"id": "dreamy_night", "name": "梦幻夜景风格，柔和的焦外虚化与温暖的光晕，营造宁静的睡眠氛围", "compatible_with": ["bedside_night", "nursery_crib"]},
            {"id": "lifestyle", "name": "生活方式摄影风格，自然光线，色彩真实，展现产品在不同场景下的使用", "compatible_with": ["living_room", "yard_stroller", "playroom_split"]},
            {"id": "commercial_product", "name": "高端电商产品摄影风格，光线均匀，细节清晰，适合产品详情页", "compatible_with": ["nursery_crib", "hotel_travel"]}
        ],
        "quality": [
            {"id": "8k_ultra", "name": "8K超高清分辨率，清晰还原产品材质、屏幕像素和细节纹理"},
            {"id": "cinematic", "name": "电影级画质，具有丰富的光影层次和自然的景深效果"},
            {"id": "c4d_render", "name": "C4D渲染品质，精细的塑料和金属材质，光影过渡自然"},
            {"id": "macro_photo", "name": "微距摄影，聚焦于产品的按键、logo和屏幕保护膜等细节"},
            {"id": "hdr", "name": "高动态范围成像，同时保留高光和暗部细节，画面更有质感"}
        ],
        "details": [
            {"id": "nursery_toys", "name": "有机棉毛绒玩具、木质摇铃、针织毯", "compatible_with": ["nursery_crib", "playroom_split"]},
            {"id": "baby_essentials", "name": "奶瓶、襁褓、安抚奶嘴", "compatible_with": ["nursery_crib", "bedside_night", "hotel_travel"]},
            {"id": "household_items", "name": "厨房料理台、沙发、电视、书本", "compatible_with": ["living_room", "kitchen_cooking"]},
            {"id": "travel_gear", "name": "便携婴儿床、折叠包、护照", "compatible_with": ["hotel_travel"]},
            {"id": "baby_parts", "name": "婴儿的小手、小脚、睡颜（不露全脸）", "compatible_with": ["nursery_crib", "bedside_night"]},
            {"id": "tech_props", "name": "额外的摄像头、充电底座、产品说明书", "compatible_with": ["playroom_split", "hotel_travel"]}
        ],
        "lighting": [
            {"id": "nightvision_infrared", "name": "夜视红外光，屏幕显示黑白画面，环境光线极低", "time": "night"},
            {"id": "warm_table_lamp", "name": "温暖的台灯光线，营造睡前的宁静氛围", "time": "night"},
            {"id": "soft_morning_light", "name": "柔和的清晨自然光，透过窗户照亮房间", "time": "day"},
            {"id": "afternoon_sunlight", "name": "午后的阳光，带有温暖的色调和明显的光影", "time": "day"},
            {"id": "evening_ambient", "name": "傍晚的环境光，混合了室内灯光和窗外的余晖", "time": "day"},
            {"id": "studio_softbox", "name": "影棚柔光箱布光，光线均匀柔和，无硬阴影", "time": "all"}
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
        
        if category == 'Audio Monitor':
            product_type = 'audio_monitor'
        elif category == 'Air Purifiers':
            product_type = 'air_purifier'
        elif category == 'Video Motion':
            product_type = 'video_motion'
        else:
            product_type = product_info.get('product_type', 'default')
        
        selling_points = product_info.get('selling_points', [])
        
        if isinstance(selling_points, str):
            selling_points = selling_points.split(",")
        
        selling_points = [sp.strip() for sp in selling_points if sp.strip()]
        selling_points_str = ", ".join(selling_points) if selling_points else "高品质婴儿产品"
        
        # 使用内部规则选择维度，确保兼容性
        selected_dimensions = self._select_dimensions(product_type)
        
        nunito_constraint = ""
        if 'Nunito' in product_description or 'nunito' in product_description:
            nunito_constraint = "4. 产品上印有bebcare字符,必须以Nunito字体呈现"
        
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
{nunito_constraint}


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
        
        if style_hint:
            prompt += f"\n风格提示：{style_hint}"
        
        return prompt.strip()


prompt_engine = PromptEngine()