# Air Purifiers 产品类型维度配置扩展计划

## 需求分析

用户需要为 Air Purifiers（空气净化器）产品类型添加新的维度组合配置，并确保当产品分类为 "Air Purifiers" 时自动使用该配置。

## 现状分析

当前代码中：
1. `DIMENSIONS` 字典包含 `default` 和 `audio_monitor` 两个配置
2. `build_image_prompt` 方法通过 `category == 'Audio Monitor'` 判断使用 `audio_monitor` 配置
3. 需要添加 `air_purifier` 配置并扩展判断逻辑

## 实现方案

### 1. 添加 Air Purifiers 维度配置

在 `DIMENSIONS` 字典中添加 `air_purifier` 配置，包含：
- **8个场景**：crib_nursery, stroller_outdoor, car_seat, travel_hotel, living_playmat, bedside_night, shopping_bag, nursing_armchair
- **7个视角**：eye_45_front, top_down_flatlay, baby_low_pov, hand_hold_portable, side_profile_cut, macro_filter_detail, stroller_pov
- **7个构图**：rule_third, center_symmetry, foreground_blur_crib, diagonal_guide, minimal_blank, narrative_lifestyle, layer_depth
- **5个风格**：dutch_minimal, warm_documentary, soft_dreamy_night, outdoor_lifestyle, commercial_product
- **5个画质**：8k_ultra_detail, cinematic_bokeh, c4d_product_render, macro_pro_shot, hdr_soft_glow
- **6个细节**：nursery_soft_toys, travel_baby_gear, night_baby_supplies, air_tech_props, baby_part_soft, household_living
- **6个光线**：soft_morning_window, golden_hour_park, soft_side_table_lamp, dim_night_ambient, soft_car_natural, studio_even_softbox

### 2. 修改 product_type 判断逻辑

修改 `build_image_prompt` 方法，扩展 category 判断：

```python
category = product_info.get('category', '')
if category == 'Audio Monitor':
    product_type = 'audio_monitor'
elif category == 'Air Purifiers':
    product_type = 'air_purifier'
else:
    product_type = product_info.get('product_type', 'default')
```

## 修改文件

- `backend/bebcare/prompt_builder/prompt_engine.py`
  - 在 DIMENSIONS 字典中添加 `air_purifier` 配置
  - 修改 build_image_prompt 方法中的 category 判断逻辑

## 兼容性关系

| 维度类型 | 兼容性关联 |
|---------|-----------|
| styles | compatible_with -> scenes |
| details | compatible_with -> scenes |
| lighting | time -> scenes.time |

## 验证步骤

1. 测试 Air Purifiers 产品使用 air_purifier 维度配置
2. 验证 Audio Monitor 产品仍使用 audio_monitor 配置
3. 验证 Night Lights 产品使用 default 配置
4. 检查维度选择的兼容性逻辑
