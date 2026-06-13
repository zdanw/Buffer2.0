
# 场景图像作为参考图功能实现计划

## 需求分析

用户需要添加一个功能：是否启用真实场景图像作为参考图。开启后，在选择参考图时会从场景图像中选择一张作为参考图，结合几张产品图像进行生成新图像。同时，当启用场景参考图时，图像模型的prompt也需要进行改进。

## 技术方案

### 后端修改

1. **schemas/generate.py** - 添加 `use_scene_reference` 字段
2. **api/generate_routes.py** - 修改参考图查询逻辑，根据开关决定是否使用场景图像
3. **prompt_builder/prompt_engine.py** - 添加场景参考图模式下的prompt生成方法
4. **generator/content_generator.py** - 根据是否使用场景参考图调用不同的prompt生成逻辑

### 前端修改

1. **api/generate.ts** - 更新 `GenerateRequest` 接口，添加新字段
2. **pages/ContentPreview.tsx** - 添加开关控件，允许用户选择是否启用场景图像参考

## 实现步骤

### 步骤1：修改后端 Schema

修改 `c:\Bebcare_Buffer2.0\backend\bebcare\schemas\generate.py`，添加 `use_scene_reference` 字段：

```python
class GenerateRequest(BaseModel):
    product_id: str
    platform: str = Field(description="目标平台")
    reference_count: int = 2
    style_hint: Optional[str] = None
    use_scene_reference: bool = False  # 新增字段：是否启用场景图像作为参考图
```

### 步骤2：修改后端 API 路由

修改 `c:\Bebcare_Buffer2.0\backend\bebcare\api\generate_routes.py`：

- 当 `use_scene_reference=True` 时：
  - 从场景图像（image_type='scene'）中随机选择 1 张作为场景参考
  - 从产品图像（image_type='product'）中选择 `reference_count` 张作为产品参考
  - 将场景图像放在参考图列表的第一位
- 当 `use_scene_reference=False` 时（默认）：
  - 保持原有逻辑，从所有图像中选择参考图

### 步骤3：修改 Prompt Engine

修改 `c:\Bebcare_Buffer2.0\backend\bebcare\prompt_builder\prompt_engine.py`：

添加新方法 `build_scene_reference_prompt`，当使用场景参考图时：
- 提示AI以场景图像作为背景场景参考
- 提示AI将产品图像中的产品放置到场景中
- 保持产品的外观和细节特征
- 融合场景氛围和产品特点

### 步骤4：修改 Content Generator

修改 `c:\Bebcare_Buffer2.0\backend\bebcare\generator\content_generator.py`：

在 `generate_image` 方法中，根据是否使用场景参考图调用不同的prompt生成逻辑：
- `use_scene_reference=True`：使用场景参考模式的prompt
- `use_scene_reference=False`：使用原有的prompt

### 步骤5：修改前端 API 类型定义

修改 `c:\Bebcare_Buffer2.0\frontend\src\api\generate.ts`，更新 `GenerateRequest` 接口：

```typescript
export interface GenerateRequest {
  product_id: string;
  platform: string;
  reference_count?: number;
  style_hint?: string;
  use_scene_reference?: boolean;  // 新增字段
}
```

### 步骤6：修改前端内容预览页面

修改 `c:\Bebcare_Buffer2.0\frontend\src\pages\ContentPreview.tsx`：
1. 添加 `useSceneReference` 状态
2. 添加开关控件（Toggle）让用户选择是否启用场景图像参考
3. 更新 `handleGenerate` 函数，传递 `use_scene_reference` 参数

## 预期效果

- 用户在内容预览页面可以看到一个"启用场景图像参考"的开关
- 开启后，生成内容时会：
  - 从场景图像中选取 1 张作为场景背景参考（放在参考图列表第一位）
  - 从产品图像中选取指定数量的产品参考图
  - 使用改进的prompt提示AI将产品融入场景中
  - 将这些图像组合作为参考图传给 AI 生成新图像
- 关闭后（默认），保持原有逻辑

## 依赖与风险

- 依赖：产品必须有场景图像才能使用此功能
- 风险：如果产品没有场景图像但开启了此功能，会优雅降级为只使用产品图像

## 文件清单

| 文件路径 | 修改类型 |
|---------|---------|
| `backend/bebcare/schemas/generate.py` | 修改 |
| `backend/bebcare/api/generate_routes.py` | 修改 |
| `backend/bebcare/prompt_builder/prompt_engine.py` | 修改 |
| `backend/bebcare/generator/content_generator.py` | 修改 |
| `frontend/src/api/generate.ts` | 修改 |
| `frontend/src/pages/ContentPreview.tsx` | 修改 |
