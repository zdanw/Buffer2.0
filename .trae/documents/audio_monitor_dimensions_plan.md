
# Audio Monitor 产品维度扩展计划

## 需求分析

用户需要为 Audio Monitor 产品类型添加专用的维度组合配置，包含场景、视角、构图、风格、画质、细节和光线等维度，并建立正确的兼容性关系。

## 现状分析

当前代码中 `DIMENSIONS` 字典仅包含一套通用配置，未区分产品类型。`_select_dimensions` 方法随机选择维度，但未考虑产品类型。

## 实现方案

### 1. 重构 DIMENSIONS 结构

将现有通用维度配置重命名为 `default`，并添加 `audio_monitor` 产品类型的专属配置：

```python
DIMENSIONS = {
    "default": { ... },  # 现有配置保持不变
    "audio_monitor": { ... }  # 新增 Audio Monitor 专属配置
}
```

### 2. 修改 `_select_dimensions` 方法

添加 `product_type` 参数，根据产品类型选择对应的维度配置：

```python
def _select_dimensions(self, product_type: str = "default") -> dict:
    dimensions = DIMENSIONS.get(product_type, DIMENSIONS["default"])
    # ... 使用对应维度进行选择
```

### 3. 更新调用位置

在 `build_image_prompt` 方法中，从 `product_info` 中获取产品类型并传递给 `_select_dimensions`。

## 修改文件

- `backend/bebcare/prompt_builder/prompt_engine.py`
  - 修改 `DIMENSIONS` 字典结构
  - 添加 `audio_monitor` 维度配置
  - 修改 `_select_dimensions` 方法签名
  - 更新 `build_image_prompt` 调用

## Audio Monitor 维度配置详情

根据用户提供的参考内容，Audio Monitor 专属维度包含：

**场景 (9个)**:
- nursery, bedside_night, stroller_outdoor, nightstand_nursery, hotel_travel, livingroom_play, nursing_chair, car_travel, kitchen_housework

**视角 (8个)**:
- eye_level_45, top_down_flatlay, baby_low_angle, parent_selfie, side_profile, macro_detail, pov_kitchen, dual_hand_hold

**构图 (7个)**:
- rule_of_thirds, symmetry_dual, foreground_blur_crib, diagonal_guide, minimal_white_space, narrative_lifestyle, layer_depth

**风格 (5个)**:
- nordic_minimal, warm_documentary, soft_dreamy, real_lifestyle, commercial_clean (均有 compatible_with)

**画质 (5个)**:
- 8k_ultra, cinematic_depth, c4d_render, macro_pro_photo, hdr_high_dynamic

**细节 (6个)**:
- nursery_toys, baby_gear, night_supplies, travel_baby_bag, baby_part_detail, household_scene (均有 compatible_with)

**光线 (6个)**:
- screen_soft_glow, morning_window_light, gold_edge_backlight, bedside_table_lamp, dim_night_ambient, golden_hour_curtain (均有 time 属性)

## 兼容性关系

| 维度类型 | 兼容性关联 |
|---------|-----------|
| styles | compatible_with -> scenes |
| details | compatible_with -> scenes |
| lighting | time -> scenes.time |

## 风险评估

- 低风险：向后兼容，默认使用原有配置
- 需要验证场景与风格、细节、光线的兼容性逻辑正确

## 测试要点

1. 当产品类型为 "audio_monitor" 时，使用新维度配置
2. 当产品类型为其他或未指定时，使用默认配置
3. 兼容性逻辑正确（