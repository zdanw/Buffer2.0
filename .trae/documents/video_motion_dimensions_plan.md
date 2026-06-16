# Video Motion 产品类型维度配置扩展计划

## 需求分析

用户需要为 Video Motion（视频监控摄像头）产品类型添加新的维度组合配置，并确保当产品分类为 "Video Motion" 时自动使用该配置。

## 现状分析

当前代码中：
1. `DIMENSIONS` 字典包含 `default`、`audio_monitor` 和 `air_purifier` 三个配置
2. `build_image_prompt` 方法通过 `category` 判断使用对应的配置
3. 需要添加 `video_motion` 配置并扩展判断逻辑

## 实现方案

### 1. 添加 Video Motion 维度配置

在 `DIMENSIONS` 字典中添加 `video_motion` 配置，包含：
- **7个场景**：nursery_crib, bedside_night, living_room, yard_stroller, playroom_split, hotel_travel, kitchen_cooking
- **7个视角**：dual_device_hero, camera_pov, parent_handheld, baby_low_angle, split_screen_detail, nightvision_closeup, wall_mounted_display
- **7个构图**：rule_of_thirds, symmetry, foreground_blur, diagonal_guide, narrative, minimalist, layered_depth
- **5个风格**：nordic_minimalist, warm_documentary, dreamy_night, lifestyle, commercial_product
- **5个画质**：8k_ultra, cinematic, c4d_render, macro_photo, hdr
- **6个细节**：nursery_toys, baby_essentials, household_items, travel_gear, baby_parts, tech_props
- **6个光线**：nightvision_infrared, warm_table_lamp, soft_morning_light, afternoon_sunlight, evening_ambient, studio_softbox

### 2. 修改 product_type 判断逻辑

修改 `build_image_prompt` 方法，扩展 category 判断：

```python
category = product_info.get('category', '')
if category == 'Audio Monitor':
    product_type = 'audio_monitor'
elif category == 'Air Purifiers':
    product_type = 'air_purifier'
elif category == 'Video Motion':
    product_type = 'video_motion'
else:
    product_type = product_info.get('product_type', 'default')
```

## 修改文件

- `backend/bebcare/prompt_builder/prompt_engine.py`
  - 在 DIMENSIONS 字典中添加 `video_motion` 配置（在 air_purifier 配置后面）
  - 修改 build_image_prompt 方法中的 category 判断逻辑

## 兼容性关系

| 维度类型 | 兼容性关联 |
|---------|-----------|
| styles | compatible_with -> scenes |
| details | compatible_with -> scenes |
| lighting | time -> scenes.time |

## 验证步骤

1. 测试 Video Motion 产品使用 video_motion 维度配置
2. 验证 Audio Monitor 产品仍使用 audio_monitor 配置
3. 验证 Air Purifiers 产品仍使用 air_purifier 配置
4. 验证 Night Lights 产品使用 default 配置
5. 检查维度选择的兼容性逻辑

## 风险评估

- 低风险：向后兼容，不影响现有产品类型配置
- 需要验证场景与风格、细节、光线的兼容性逻辑正确
