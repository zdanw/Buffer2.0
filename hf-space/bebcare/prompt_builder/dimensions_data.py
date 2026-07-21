DIMENSIONS = {
    "night_lights": {
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
            {"id": "golden_hour_diffuse", "name": "傍晚金色时刻柔和漫射光线，透过窗帘缝隙洒落在监护主机上，温馨黄昏氛围", "time": "day"}
        ]
    },
    "air_purifier": {
        "scenes": [
            {"id": "nursery", "name": "温馨原木风婴儿房，白色婴儿床旁放置空气净化器", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "bedroom_parent", "name": "主卧床头柜，空气净化器与台灯并排摆放，安静夜间睡眠场景", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "livingroom_family", "name": "客厅沙发旁，空气净化器放在地毯上，家人在客厅休闲，背景虚化", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "baby_play", "name": "婴儿爬行垫旁，空气净化器靠近围栏，宝宝在安全区域玩耍", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "home_office", "name": "居家办公书桌旁，空气净化器放在桌面角落，背景可见电脑屏幕", "time": "day", "lighting": ["natural", "soft"]},
            {"id": "hotel_travel", "name": "旅行酒店客房，便携空气净化器放在床头柜，展现出行必备", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "kitchen_area", "name": "开放式厨房餐桌旁，空气净化器有效净化烹饪油烟残留", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "car_travel", "name": "车载出行，空气净化器放在中控扶手或后座，打造洁净车内环境", "time": "day", "lighting": ["natural", "bright"]}
        ],
        "viewpoints": [
            {"id": "eye_level_45", "name": "45°平视产品特写，展示机身圆润曲线、触控面板与出风口设计"},
            {"id": "top_down_flatlay", "name": "俯拍平铺视角，空气净化器放在浅色木质桌面，搭配绿植与母婴小物件"},
            {"id": "baby_low_angle", "name": "婴儿平视低角度，仰拍放置在地面的空气净化器，凸显安全设计"},
            {"id": "parent_selfie", "name": "第一人称自拍视角，一只手轻触净化器触控面板，背景可见温馨居家环境"},
            {"id": "side_profile", "name": "产品侧视角，展示机身厚度、进风口栅格与圆润边角设计"},
            {"id": "macro_detail", "name": "微距特写，聚焦触控面板按钮、指示灯与品牌logo"},
            {"id": "pov_livingroom", "name": "客厅第一视角，镜头看向沙发旁的空气净化器，背景虚化家人活动"},
            {"id": "dual_product", "name": "两台净化器并排摆放，展示不同尺寸或颜色选择"}
        ],
        "compositions": [
            {"id": "rule_of_thirds", "name": "三分构图，净化器放置画面右下区域，左侧留白搭配柔和环境光"},
            {"id": "symmetry_center", "name": "中心对称构图，净化器居中摆放，两侧对称布置绿植或装饰品"},
            {"id": "foreground_blur", "name": "前景虚化构图，透过婴儿床栏杆或绿植对焦净化器"},
            {"id": "diagonal_flow", "name": "对角线构图，从净化器出风口延伸出清新气流视觉效果"},
            {"id": "minimal_white_space", "name": "极简留白构图，浅纯色背景，净化器居中，突出产品设计"},
            {"id": "narrative_lifestyle", "name": "生活叙事构图，部分入镜宝宝玩耍+净化器+居家环境"},
            {"id": "layer_depth", "name": "前后景分层构图，前景净化器清晰，背景虚化居家生活场景"}
        ],
        "styles": [
            {"id": "nordic_minimal", "name": "北欧简约设计美学，哑光白色柔和质感，圆润边角，干净治愈", "compatible_with": ["nursery", "bedroom_parent", "hotel_travel"]},
            {"id": "warm_documentary", "name": "家庭纪实胶片摄影风，轻微颗粒感，暖调原生色彩，真实生活场景", "compatible_with": ["livingroom_family", "baby_play", "kitchen_area"]},
            {"id": "soft_dreamy", "name": "梦幻柔焦氛围感风格，浅景深背景虚化，适合夜间睡眠场景", "compatible_with": ["bedroom_parent", "nursery", "hotel_travel"]},
            {"id": "real_lifestyle", "name": "写实生活方式摄影，自然日光原生色调，还原日常居家使用场景", "compatible_with": ["livingroom_family", "baby_play", "car_travel"]},
            {"id": "commercial_clean", "name": "高端电商产品商业摄影风格，均匀柔光，细腻材质还原", "compatible_with": ["nursery", "home_office"]}
        ],
        "quality": [
            {"id": "8k_ultra", "name": "8K超高清分辨率，精准还原哑光塑料机身、触控面板、出风口细节"},
            {"id": "cinematic_depth", "name": "电影级光影景深，柔和焦外虚化，明暗层次丰富"},
            {"id": "c4d_render", "name": "C4D写实三维渲染，细腻材质质感，光影过渡自然柔和"},
            {"id": "macro_pro_photo", "name": "专业微距商业摄影，捕捉触控按钮、指示灯、logo细节"},
            {"id": "hdr_high_dynamic", "name": "HDR高动态范围成像，高光暗部细节完整保留"}
        ],
        "details": [
            {"id": "nursery_toys", "name": "针织安抚玩偶、纯棉盖毯、原木摇铃，温馨婴儿房道具", "compatible_with": ["nursery", "baby_play"]},
            {"id": "baby_gear", "name": "婴儿布艺绘本、硅胶奶嘴、棉麻收纳筐，生活化母婴物件", "compatible_with": ["nursery", "bedroom_parent"]},
            {"id": "green_plants", "name": "琴叶榕、龟背竹、多肉植物，清新自然居家装饰", "compatible_with": ["livingroom_family", "home_office"]},
            {"id": "travel_bag", "name": "便携收纳袋、充电线，突出产品便携属性", "compatible_with": ["hotel_travel", "car_travel"]},
            {"id": "home_decor", "name": "香薰蜡烛、装饰画、布艺抱枕，温馨居家氛围道具", "compatible_with": ["bedroom_parent", "livingroom_family"]}
        ],
        "lighting": [
            {"id": "soft_night_glow", "name": "净化器指示灯微弱柔和光晕，房间弱光夜间氛围", "time": "night"},
            {"id": "morning_window_light", "name": "清晨窗边柔和漫射自然光，光线通透温暖", "time": "day"},
            {"id": "gold_edge_backlight", "name": "逆光金色轮廓光，勾勒机身圆润曲线", "time": "day"},
            {"id": "bedside_table_lamp", "name": "卧室暖光台灯侧逆光，柔和漫射光影", "time": "night"},
            {"id": "dim_night_ambient", "name": "弱暗卧室环境，仅依靠净化器指示灯与远处床头小夜灯", "time": "night"},
            {"id": "golden_hour_diffuse", "name": "傍晚金色时刻柔和漫射光线，温馨黄昏氛围", "time": "day"}
        ]
    },
    "video_motion": {
        "scenes": [
            {"id": "nursery", "name": "温馨原木风婴儿房，白色婴儿床上方安装视频监护摄像头", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "bedside_night", "name": "主卧床头柜，家长端屏幕显示宝宝实时画面，婴儿在隔壁熟睡", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "livingroom_play", "name": "客厅爬行游戏垫，摄像头从高处俯拍，宝宝在围栏内玩耍", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "stroller_outdoor", "name": "婴儿推车安装便携摄像头，户外公园遛娃远程监护", "time": "day", "lighting": ["natural", "bright"]},
            {"id": "home_office", "name": "居家办公场景，家长端放在桌面，一边工作一边查看宝宝画面", "time": "day", "lighting": ["natural", "soft"]},
            {"id": "hotel_travel", "name": "旅行酒店客房，便携摄像头安装在临时婴儿床旁", "time": "indoor", "lighting": ["warm", "soft"]},
            {"id": "nursing_chair", "name": "婴儿房哺乳椅旁，昏暗睡前场景，摄像头记录温馨亲子时光", "time": "night", "lighting": ["dim", "warm"]},
            {"id": "car_travel", "name": "车载出行，摄像头安装在儿童安全座椅旁，家长端放在中控", "time": "day", "lighting": ["natural", "bright"]}
        ],
        "viewpoints": [
            {"id": "camera_pov", "name": "摄像头视角，模拟从高处俯拍婴儿床内的宝宝"},
            {"id": "parent_view_screen", "name": "家长端屏幕视角，展示实时视频画面与温度显示"},
            {"id": "eye_level_45", "name": "45°平视产品特写，展示摄像头球形设计、夜视灯与麦克风"},
            {"id": "top_down_flatlay", "name": "俯拍平铺视角，摄像头与家长端主机铺在针织盖毯上"},
            {"id": "baby_low_angle", "name": "婴儿平视低角度，仰拍墙上安装的摄像头"},
            {"id": "macro_detail", "name": "微距特写，聚焦摄像头镜头、夜视红外灯与品牌logo"},
            {"id": "side_profile", "name": "产品侧视角，展示摄像头底座、旋转轴与线缆"},
            {"id": "dual_screen", "name": "双屏展示，手机APP画面与家长端屏幕同步显示"}
        ],
        "compositions": [
            {"id": "rule_of_thirds", "name": "三分构图，摄像头放置画面右上区域，下方显示家长端屏幕"},
            {"id": "symmetry_center", "name": "中心对称构图，摄像头居中，两侧对称布置婴儿房软装"},
            {"id": "foreground_blur_crib", "name": "前景虚化构图，透过婴儿床栏杆对焦摄像头"},
            {"id": "diagonal_guide", "name": "对角线构图，从摄像头延伸至家长端的无线连接视觉"},
            {"id": "minimal_white_space", "name": "极简留白构图，浅纯色背景，摄像头居中突出设计"},
            {"id": "narrative_lifestyle", "name": "生活叙事构图，部分入镜宝宝+摄像头+家长使用场景"},
            {"id": "layer_depth", "name": "前后景分层构图，前景家长端屏幕清晰，背景摄像头虚化"}
        ],
        "styles": [
            {"id": "nordic_minimal", "name": "北欧简约设计美学，哑光白色球形摄像头，干净治愈", "compatible_with": ["nursery", "bedside_night", "hotel_travel"]},
            {"id": "warm_documentary", "name": "家庭纪实胶片摄影风，轻微颗粒感，真实生活场景", "compatible_with": ["livingroom_play", "nursing_chair", "stroller_outdoor"]},
            {"id": "soft_dreamy", "name": "梦幻柔焦氛围感风格，浅景深背景虚化，适合夜间场景", "compatible_with": ["bedside_night", "nursery", "nursing_chair"]},
            {"id": "real_lifestyle", "name": "写实生活方式摄影，自然日光原生色调，还原日常使用场景", "compatible_with": ["livingroom_play", "stroller_outdoor", "car_travel"]},
            {"id": "commercial_clean", "name": "高端电商产品商业摄影风格，均匀柔光，细腻材质还原", "compatible_with": ["nursery", "home_office"]}
        ],
        "quality": [
            {"id": "8k_ultra", "name": "8K超高清分辨率，精准还原球形机身、镜头、红外灯细节"},
            {"id": "cinematic_depth", "name": "电影级光影景深，柔和焦外虚化，明暗层次丰富"},
            {"id": "c4d_render", "name": "C4D写实三维渲染，细腻材质质感，光影过渡自然"},
            {"id": "macro_pro_photo", "name": "专业微距商业摄影，捕捉镜头、按键、logo细节"},
            {"id": "hdr_high_dynamic", "name": "HDR高动态范围成像，夜视模式与日间模式效果"}
        ],
        "details": [
            {"id": "nursery_toys", "name": "针织安抚玩偶、纯棉盖毯、原木摇铃，温馨婴儿房道具", "compatible_with": ["nursery", "livingroom_play"]},
            {"id": "baby_gear", "name": "婴儿布艺绘本、硅胶奶嘴、棉麻收纳筐，生活化母婴物件", "compatible_with": ["nursery", "bedside_night"]},
            {"id": "night_supplies", "name": "恒温奶瓶、折叠纱布襁褓、婴儿面霜，夜间育儿用品", "compatible_with": ["bedside_night", "nursing_chair"]},
            {"id": "travel_bag", "name": "便携收纳袋、充电线、安装支架，突出便携属性", "compatible_with": ["stroller_outdoor", "hotel_travel", "car_travel"]},
            {"id": "baby_part_detail", "name": "熟睡婴儿的小手、小脚局部入镜，营造温柔守护氛围", "compatible_with": ["bedside_night", "nursing_chair"]}
        ],
        "lighting": [
            {"id": "infrared_night", "name": "夜视模式红外光线，微弱不可见光，守护宝宝睡眠", "time": "night"},
            {"id": "morning_window_light", "name": "清晨窗边柔和漫射自然光，光线通透温暖", "time": "day"},
            {"id": "gold_edge_backlight", "name": "逆光金色轮廓光，勾勒球形摄像头曲线", "time": "day"},
            {"id": "bedside_table_lamp", "name": "卧室暖光台灯侧逆光，柔和漫射光影", "time": "night"},
            {"id": "dim_night_ambient", "name": "弱暗卧室环境，摄像头夜视灯微弱红光", "time": "night"},
            {"id": "golden_hour_diffuse", "name": "傍晚金色时刻柔和漫射光线，温馨黄昏氛围", "time": "day"}
        ]
    }
}